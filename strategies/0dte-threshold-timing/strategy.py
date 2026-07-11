#!/usr/bin/env python
"""
PIPELINE ENTRY POINT — 0DTE / short-dated option threshold-timing study.

A DESCRIPTIVE historical study (no live trading, no orders). For each long
option (call and put) in the Mag-7 + ORCL + AMD universe it measures, over
historical minute quotes, WHEN the mark reaches a ladder of profit thresholds
(+20…+100%) and HOW LONG that exit window stays open — producing an entry/exit
playbook per symbol, direction, expiry regime, entry-time window and moneyness.

Output contract (the rest of the pipeline depends on these):
  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json        machine-readable summary  (REQUIRED)
       - analysis/output/     threshold_by_symbol/, optimal_entry.csv, summary.md,
                              run_config.json
       - sequential/          Mode B & Mode C per-symbol CSVs
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

Data: real top-of-book option quotes from Alpaca when credentials are present;
otherwise a clearly-labelled SIMULATED (Black-Scholes) fallback so the pipeline
never goes silent. The SIMULATED numbers are NOT a real edge.

Run by hand:  python strategy.py     (uses ./output; SIMULATED without keys)
Use `python`, not `python3` (this repo targets Windows).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone as dt_timezone

import pandas as pd

from config import Config
from data import schema as _schema
from data import alpaca_quotes as _alp
from core import expiry as _exp
from core.sweep import run_sweep
from core.aggregate import bucketed_table, dow_rollup
from core.optimizer import optimal_entry_surface
from core.sequential import run_mode_b
from core.walkforward import run_mode_c
from core import validation as _val
from core.report import build_summary_md


def results_dir() -> str:
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


def _load_data(cfg: Config, log) -> tuple:
    """Return (contract_df, source_label). Real Alpaca quotes if available, else
    the labelled SIMULATED fallback."""
    if _alp.credentials_present():
        log("[data] Alpaca credentials present — fetching real option quotes …")
        raw = _alp.fetch_universe(cfg, log=log)
        if raw is not None and not raw.empty:
            return _schema.validate_contract(raw, cfg), _schema.SOURCE_REAL
        log("[data] real fetch returned nothing — falling back to SIMULATED")
    else:
        log("[data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — using SIMULATED fallback")
    sim = _schema.simulate_quote_frame(cfg)
    return _schema.validate_contract(sim, cfg), _schema.SOURCE_SIM


def _write_csv(df: pd.DataFrame, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    (df if df is not None else pd.DataFrame()).to_csv(path, index=False)


def run(cfg: Config, out_dir: str, log) -> dict:
    df, source_label = _load_data(cfg, log)
    if df.empty:
        raise RuntimeError("no usable contract-minute data (real or simulated)")

    session_dates = sorted(pd.to_datetime(df[cfg.col_ts]).dt.date.unique())
    date_min, date_max = str(session_dates[0]), str(session_dates[-1])
    n_sessions = len(session_dates)
    session_open = 9 * 60 + 30

    ao = os.path.join(out_dir, "analysis", "output")
    seqd = os.path.join(out_dir, "sequential")
    os.makedirs(os.path.join(ao, "threshold_by_symbol"), exist_ok=True)
    os.makedirs(seqd, exist_ok=True)

    # Process ONE SYMBOL AT A TIME so peak memory is a single symbol's instance
    # surface, not the whole universe's. Only the compact result tables are kept
    # and concatenated; the raw per-symbol instances are discarded each loop.
    log(f"[sweep] entry-sweep + Modes A/B/C over {len(df):,} contract-minutes, per symbol …")
    bucketed_parts, rollup_parts, optimal_parts = [], [], []
    modeb_summary_parts, modec_perf_parts = [], []
    expiry_index, counts = {}, {}
    val_agg = {"mm_violations": [], "mm_compared": 0, "regime_problems": [],
               "dupes": 0, "spot_checked": 0, "spot_mismatch": 0,
               "per_symbol_0dte_share": {}}
    n_instances_total = 0

    for sym in cfg.tickers:
        sym_df = df[df[cfg.col_symbol] == sym]
        if sym_df.empty:
            continue
        instances, meta = run_sweep(sym_df, cfg)
        cnt = meta["counts"].get(sym, {"rows": len(sym_df), "instances": 0, "buckets": 0})
        counts[sym] = cnt
        expiry_index.update(meta["expiry_index"])
        log(f"  {sym:>6}: rows={cnt['rows']:>8}  instances={cnt['instances']:>8}  "
            f"buckets={cnt['buckets']:>4}")
        if instances.empty:
            continue
        n_instances_total += len(instances)

        bucketed = bucketed_table(instances, cfg)
        rollup = dow_rollup(instances, cfg)
        optimal = optimal_entry_surface(instances, cfg)
        mode_b = run_mode_b(instances, cfg, session_open)
        mode_c = run_mode_c(instances, cfg, session_open)
        validation = _val.run_all(sym_df, instances, bucketed, cfg)

        # per-symbol deliverables
        _write_csv(bucketed, os.path.join(ao, "threshold_by_symbol", f"{sym}.csv"))
        _write_csv(mode_b["trades"], os.path.join(seqd, f"{sym}_trades.csv"))
        _write_csv(mode_b["daily"], os.path.join(seqd, f"{sym}_daily.csv"))
        _write_csv(mode_c["trades"], os.path.join(seqd, f"{sym}_strategy_trades.csv"))
        _write_csv(mode_c["perf"], os.path.join(seqd, f"{sym}_strategy_perf.csv"))

        # accumulate compact tables for universe-level deliverables
        bucketed_parts.append(bucketed)
        rollup_parts.append(rollup)
        optimal_parts.append(optimal)
        if not mode_b["summary"].empty:
            modeb_summary_parts.append(mode_b["summary"])
        if not mode_c["perf"].empty:
            modec_perf_parts.append(mode_c["perf"])

        mm = validation["mid_ge_market"]
        val_agg["mm_violations"].extend(mm["violations"])
        val_agg["mm_compared"] += mm["n_compared"]
        val_agg["regime_problems"].extend(validation["regimes"]["problems"])
        val_agg["per_symbol_0dte_share"].update(
            validation["regimes"].get("per_symbol_0dte_share", {}))
        val_agg["dupes"] += validation["no_overlap"]["n_dupes"]
        val_agg["spot_checked"] += validation["spot_check"]["checked"]
        val_agg["spot_mismatch"] += len(validation["spot_check"]["mismatches"])
        del instances

    def _concat(parts):
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    bucketed_all = _concat(bucketed_parts)
    optimal = _concat(optimal_parts)
    rollup = _concat(rollup_parts)
    modeb_summary = _concat(modeb_summary_parts)
    modec_perf = _concat(modec_perf_parts)

    _write_csv(optimal, os.path.join(ao, "optimal_entry.csv"))
    _write_csv(rollup, os.path.join(ao, "dow_rollup.csv"))

    # reconstruct the aggregated validation report
    validation = {
        "mid_ge_market": {"ok": len(val_agg["mm_violations"]) == 0,
                          "violations": val_agg["mm_violations"],
                          "n_compared": val_agg["mm_compared"]},
        "regimes": {"ok": len(val_agg["regime_problems"]) == 0,
                    "problems": val_agg["regime_problems"],
                    "per_symbol_0dte_share": val_agg["per_symbol_0dte_share"]},
        "no_overlap": {"ok": val_agg["dupes"] == 0, "n_dupes": val_agg["dupes"]},
        "spot_check": {"ok": val_agg["spot_mismatch"] == 0,
                       "checked": val_agg["spot_checked"], "mismatches": []},
    }

    # detected per-symbol expiry cadence
    cadence = _exp.detect_cadence(expiry_index)
    meta = {"counts": counts}
    bucketed = bucketed_all
    mode_b = {"summary": modeb_summary}
    mode_c = {"perf": modec_perf}

    # run_config.json
    run_config = {
        "universe": cfg.tickers,
        "date_range": {"start": date_min, "end": date_max, "n_sessions": n_sessions},
        "thresholds_pct": cfg.thresholds_pct,
        "entry_sweep": {"start_min": cfg.entry_start_min, "end_min": cfg.entry_end_min,
                        "step_min": cfg.entry_step_min},
        "fill_modes": cfg.fill_modes,
        "strike_band": cfg.strike_band,
        "walk_forward": {"train_weeks": cfg.train_weeks, "test_weeks": cfg.test_weeks,
                         "expanding": cfg.expanding_window,
                         "max_exit_rule": list(cfg.max_exit_rule)},
        "detected_expiry_cadence": cadence,
        "row_counts": meta["counts"],
        "data_source": source_label,
    }
    with open(os.path.join(ao, "run_config.json"), "w", encoding="utf-8") as f:
        json.dump(run_config, f, indent=2, default=str)

    # summary.md
    ctx = {
        "cfg": cfg, "source_label": source_label,
        "date_min": date_min, "date_max": date_max, "n_sessions": n_sessions,
        "optimal_entry": optimal, "bucketed": bucketed,
        "mode_b_summary": mode_b["summary"], "mode_c_perf": mode_c["perf"],
        "validation": validation,
    }
    summary_md = build_summary_md(ctx)
    with open(os.path.join(ao, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_md)

    # ── metrics.json (REQUIRED, at results root) ─────────────────────────────
    mm = validation["mid_ge_market"]
    n_pos_c = 0
    if mode_c["perf"] is not None and not mode_c["perf"].empty:
        p = mode_c["perf"]
        n_pos_c = int(((p["fill_mode"] == "market") & (p["expectancy_per_trade"] > 0)).sum())
    metrics = {
        "status": "ok",
        "strategy": "0dte-threshold-timing",
        "data_source": source_label,
        "date_range": {"start": date_min, "end": date_max, "n_sessions": n_sessions},
        "universe": cfg.tickers,
        "n_contract_minutes": int(len(df)),
        "n_instances": int(n_instances_total),
        "n_buckets": int(bucketed.groupby(
            ["symbol", "direction", "fill_mode", "regime", "entry_bucket", "moneyness"]
        ).ngroups) if not bucketed.empty else 0,
        "mode_c_positive_market_combos": n_pos_c,
        "validation": {
            "mid_ge_market_ok": mm["ok"],
            "mid_ge_market_violation_groups": len(mm["violations"]),
            "mid_ge_market_instances_compared": mm["n_compared"],
            "regimes_ok": validation["regimes"]["ok"],
            "no_overlap_ok": validation["no_overlap"]["ok"],
            "spot_check_ok": validation["spot_check"]["ok"],
        },
        "generated_at": datetime.now(dt_timezone.utc).isoformat(),
    }
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    log("\n" + "=" * 62)
    log("  0DTE THRESHOLD-TIMING — done")
    log(f"  data      : {source_label}")
    log(f"  range     : {date_min} → {date_max}  ({n_sessions} sessions)")
    log(f"  instances : {n_instances_total:,}   buckets: {metrics['n_buckets']:,}")
    log(f"  validation: mid≥market={mm['ok']} regimes={validation['regimes']['ok']} "
        f"overlap_ok={validation['no_overlap']['ok']} spotcheck={validation['spot_check']['ok']}")
    log(f"  Mode C +ve market combos: {n_pos_c}")
    log("=" * 62 + "\n")
    return metrics


def main() -> int:
    cfg = Config()
    out_dir = results_dir()
    try:
        metrics = run(cfg, out_dir, log=lambda *a: print(*a, flush=True))
    except Exception:
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "0dte-threshold-timing",
                   "error": tb.splitlines()[-1],
                   "generated_at": datetime.now(dt_timezone.utc).isoformat()}
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(tb, file=sys.stderr)
        print("===STRATEGY_SUMMARY_JSON===")
        print(json.dumps(metrics))
        print("===END_SUMMARY===")
        return 1

    print("===STRATEGY_SUMMARY_JSON===")
    print(json.dumps(metrics))
    print("===END_SUMMARY===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
