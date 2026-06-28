#!/usr/bin/env python
"""
PIPELINE ADAPTER for the TSLA Friday optimal entry/exit time-frame study.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone analysis in backtest_timeframe.py / timeframe_engine.py
and emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - trades.csv        per-Friday ledger (both calls and puts)
       - equity_curve.png  cumulative P&L chart
     plus the rich per-option-type *.txt / *.csv / *_outliers_removed.txt the
     standalone run produces (RESULTS_DIR is pointed at the same directory).
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The actual research logic lives in timeframe_engine.py — this file only adapts it
to the pipeline. Run by hand with `python backtest_timeframe.py` for the full
terminal report, or `python strategy.py` to also produce the contract artifacts.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone as dt_timezone


def results_dir() -> str:
    """Where artifacts go. Pipeline sets STRATEGY_RESULTS_DIR; CLI uses ./output."""
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


def _source_label(rows) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED real + Black-Scholes sim"
    if "REAL" in srcs:
        return "REAL Alpaca option bars"
    if "SIM" in srcs:
        return "SIMULATED (Black-Scholes)"
    return "NONE"


def _drawdown_and_sharpe(pnls):
    """Pure-Python max drawdown and a per-trade Sharpe (no numpy dependency)."""
    if not pnls:
        return 0.0, 0.0
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    n = len(pnls)
    mean = sum(pnls) / n
    if n > 1:
        var = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        std = var ** 0.5
        sharpe = (mean / std) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return round(max_dd, 2), round(sharpe, 3)


def _frame_summary(frame, summ, rows=None):
    from timeframe_engine import frame_label
    data_source = _source_label(rows or [])
    if frame is None:
        return {"entry_frame": None, "exit_frame": None, "n_trades": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                "best_day": 0.0, "worst_day": 0.0,
                "return_on_spend": 0.0, "data_source": data_source}
    cost = summ.get("total_cost", 0.0)
    roi = (summ["total_pnl"] / cost) if cost else 0.0
    return {
        "entry_frame": frame_label(frame["es"], frame["ee"]),
        "exit_frame": frame_label(frame["xs"], frame["xe"]),
        "entry_minutes": frame["ee"] - frame["es"],
        "exit_minutes": frame["xe"] - frame["xs"],
        "n_trades": summ["n"], "wins": summ["wins"],
        "win_rate": round(summ["win_rate"], 4),
        "total_pnl": round(summ["total_pnl"], 2),
        "avg_pnl": round(summ["avg_pnl"], 2),
        "best_day": round(summ["best"], 2), "worst_day": round(summ["worst"], 2),
        "premium_spent": round(cost, 2), "return_on_spend": round(roi, 4),
        "data_source": data_source,
    }


def _write_trades_csv(path, all_results, rows_getter):
    """Write a per-Friday ledger CSV. rows_getter(res) selects which row set
    (the normal pass or the outliers-removed pass) to write."""
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "opt_type", "contract_symbol", "strike", "source",
                    "entry_frame", "entry_price", "exit_frame", "exit_price",
                    "payoff_per_share", "contracts", "cost_dollars",
                    "pnl_dollars", "profitable", "note"])
        for key, res in sorted(all_results.items(), key=lambda kv: kv[0][1]):
            if not res:
                continue
            for r in rows_getter(res):
                w.writerow([r["date"], r["opt_type"], r["contract_symbol"],
                            r["strike"], r["source"], r["entry_frame"],
                            r["entry_price"], r["exit_frame"], r["exit_price"],
                            r["payoff_per_share"], r["contracts"],
                            r["cost_dollars"], r["pnl_dollars"], r["profitable"],
                            r["note"]])


def save_artifacts(out_dir, all_results, outlier_max=None):
    """trades.csv (combined ledger) + trades_outliers_removed.csv + equity_curve.png.

    trades_outliers_removed.csv mirrors trades.csv but uses the engine's
    outliers-removed pass: each option type re-optimized with winning trades over
    `outlier_max` dropped (same logic that produces the *_outliers_removed.txt files).
    """
    # Combined per-Friday ledger (normal pass — with outliers)
    _write_trades_csv(os.path.join(out_dir, "trades.csv"), all_results,
                      lambda res: res.get("rows", []))

    # Outliers-removed ledger (re-optimized pass with winning outliers dropped)
    if outlier_max is not None:
        _write_trades_csv(
            os.path.join(out_dir, "trades_outliers_removed.csv"), all_results,
            lambda res: (res.get("excl") or {}).get("rows", []))

    # equity_curve.png — one cumulative line per option type (chart is optional).
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        plotted = False
        for (ticker, opt_type), res in sorted(all_results.items(),
                                              key=lambda kv: kv[0][1]):
            if not res:
                continue
            pnls = [r["pnl_dollars"] for r in res["rows"] if r["pnl_dollars"] != ""]
            if not pnls:
                continue
            equity, cum = [], 0.0
            for p in pnls:
                cum += p
                equity.append(cum)
            label = f"{ticker} {'CALL' if opt_type == 'C' else 'PUT'}s"
            ax.plot(range(1, len(equity) + 1), equity, lw=1.8, label=label)
            plotted = True
        if plotted:
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — TSLA Friday optimal entry/exit frames")
            ax.set_xlabel("Trade # (Fridays)")
            ax.set_ylabel("Cumulative P&L ($)")
            ax.legend()
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "equity_curve.png"), dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def _aggregate(all_rows):
    """Overall metrics over a flat list of per-day rows."""
    pnls = [r["pnl_dollars"] for r in all_rows if r["pnl_dollars"] != ""]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls)
    max_dd, sharpe = _drawdown_and_sharpe(pnls)
    return {
        "n_trades": n,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / n, 2) if n else 0.0,
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "data_source": _source_label(all_rows),
    }


def _pass_metrics(all_results, pass_key):
    """Build the {overall + calls + puts} block for one pass.

    pass_key=None  -> normal pass (with outliers): res["rows"]/["frame"]/["summ"]
    pass_key="excl" -> outliers-removed pass:        res["excl"]["..."]
    """
    all_rows = []
    per_type = {}
    removed_dates = []
    for (ticker, opt_type), res in all_results.items():
        src = (res or {}) if pass_key is None else (res or {}).get("excl") or {}
        rows = src.get("rows", []) if res else []
        all_rows.extend(rows)
        key = "calls" if opt_type == "C" else "puts"
        per_type[key] = _frame_summary(src.get("frame") if res else None,
                                       src.get("summ", {}) if res else {}, rows)
        if pass_key == "excl" and res:
            removed_dates.extend((res.get("excl") or {}).get("removed") or [])
    block = _aggregate(all_rows)
    block["calls"] = per_type.get("calls")
    block["puts"] = per_type.get("puts")
    if pass_key == "excl":
        block["removed_dates"] = removed_dates
    return block


def build_metrics(all_results, lookback_days, target_spend, outlier_max):
    """Aggregate the per-option-type results into the contract metrics dict.

    Top-level fields cover the normal pass (with outliers); the nested
    `outliers_removed` block carries the re-optimized, outliers-removed pass so
    Oracle can render both 'With Outliers' and 'Without Outliers' sections.
    """
    normal = _pass_metrics(all_results, pass_key=None)
    metrics = {
        "status": "ok",
        "strategy": "tsla-friday-timeframe",
        "ticker": "TSLA",
        "day": "Friday",
        "session": "9:30 AM-4:00 PM ET",
        "lookback_days": lookback_days,
        "target_spend": target_spend,
        "outlier_max": outlier_max,
        **normal,
    }
    if outlier_max is not None:
        excl = _pass_metrics(all_results, pass_key="excl")
        excl["outlier_max"] = outlier_max
        metrics["outliers_removed"] = excl
    return metrics


def print_summary(metrics):
    c = metrics.get("calls") or {}
    p = metrics.get("puts") or {}
    print("\n" + "=" * 60)
    print("  STRATEGY SUMMARY — TSLA Friday optimal entry/exit frames")
    print("=" * 60)
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Trades      : {metrics.get('n_trades')}")
    print(f"  Win rate    : {metrics.get('win_rate', 0) * 100:.1f}%")
    print(f"  Total P&L   : ${metrics.get('total_pnl', 0):,.2f}")
    print(f"  Avg / trade : ${metrics.get('avg_pnl', 0):,.2f}")
    print(f"  Max drawdown: ${metrics.get('max_drawdown', 0):,.2f}")
    print(f"  CALLS       : enter {c.get('entry_frame')}  exit {c.get('exit_frame')}"
          f"  (win {c.get('win_rate', 0) * 100:.0f}%, ${c.get('total_pnl', 0):,.0f})")
    print(f"  PUTS        : enter {p.get('entry_frame')}  exit {p.get('exit_frame')}"
          f"  (win {p.get('win_rate', 0) * 100:.0f}%, ${p.get('total_pnl', 0):,.0f})")
    print("=" * 60 + "\n")
    # Machine-readable block — Oracle / log scrapers key off these markers.
    print("===STRATEGY_SUMMARY_JSON===")
    print(json.dumps(metrics))
    print("===END_SUMMARY===")


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    out_dir = results_dir()

    # Surface data provenance up front (the engine also degrades gracefully).
    if not os.environ.get("ALPACA_API_KEY") or not (
            os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")):
        print("  [data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — results will "
              "fall back to Black-Scholes simulation (yfinance has no option bars).")

    try:
        import timeframe_engine as te
        from backtest_timeframe import (
            LOOKBACK_DAYS, TARGET_SPEND, OUTLIER_MAX,
            size_fn, score_key, eligible,
        )

        # Deliver the rich per-option-type TXT/CSV into the results dir too.
        te.RESULTS_DIR = out_dir

        all_results = te.run_timeframe(
            lookback_days=LOOKBACK_DAYS,
            method_label="MAX EXPECTED PROFIT, target-spend sized (win_rate × avg_payoff)",
            score_key=score_key,
            eligible=eligible,
            size_fn=size_fn,
            file_tag="tsla_friday_timeframe",
            outlier_max=OUTLIER_MAX,
            header_extra=(
                f"Position sizing: contracts = ceil(${TARGET_SPEND:.2f} / "
                f"mean(entry_frame)), min 1. Frames are arbitrary [start, end] "
                f"windows; price = mean of the 1-min closes inside the frame."
            ),
        )

        metrics = build_metrics(all_results, LOOKBACK_DAYS, TARGET_SPEND, OUTLIER_MAX)
        save_artifacts(out_dir, all_results, OUTLIER_MAX)
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "tsla-friday-timeframe",
                   "error": f"{type(e).__name__}: {e}", "traceback": tb}
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(tb, file=sys.stderr)
        print("===STRATEGY_SUMMARY_JSON===")
        print(json.dumps(metrics))
        print("===END_SUMMARY===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
