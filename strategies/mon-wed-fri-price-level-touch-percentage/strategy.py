#!/usr/bin/env python
"""
PIPELINE ADAPTER for the Friday price-level-touch study.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone analysis in backtest_level_touch.py /
level_touch_engine.py and emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - swings.csv        per-Friday × per-reference touch/swing ledger
       - hit_rates.png     +/- touch-rate bars per reference time (optional)
     plus the rich per-ticker level_touch_<ticker>_*.txt and the combined
     touch_summary_*.csv / swings_*.csv the standalone run produces (RESULTS_DIR
     is pointed at the same directory).
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The actual research logic lives in analysis/level_touch.py + level_touch_engine.py
— this file only adapts it to the pipeline. Run by hand with
`python backtest_level_touch.py` for the full terminal report, or
`python strategy.py` to also produce the contract artifacts.

NOTE: this is a stock price-level study — there are no options and no P&L, so the
template's target_spend / outlier_max are carried as inert documented metadata.
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


def _ref_block(summary: dict) -> dict:
    """One reference label's stats, rounded for metrics.json. Swings are reported
    primarily as a fraction of the reference price, with the dollar move kept
    alongside (max_*_swing is the biggest single-day % move, with that day's $)."""
    return {
        "sessions": summary["n"],
        "up_hits": summary["up_hits"], "up_rate": round(summary["up_rate"], 4),
        "down_hits": summary["down_hits"], "down_rate": round(summary["down_rate"], 4),
        "both_hits": summary["both"], "both_rate": round(summary["both_rate"], 4),
        "neither_hits": summary["neither"],
        "neither_rate": round(summary["neither_rate"], 4),
        "avg_up_swing_pct": round(summary["avg_up_swing_pct"], 6),
        "avg_down_swing_pct": round(summary["avg_down_swing_pct"], 6),
        "max_up_swing_pct": round(summary["max_up_swing_pct"], 6),
        "max_down_swing_pct": round(summary["max_down_swing_pct"], 6),
        "avg_up_swing": round(summary["avg_up_swing"], 4),
        "avg_down_swing": round(summary["avg_down_swing"], 4),
        "max_up_swing": round(summary["max_up_swing_at_pct"], 4),
        "max_down_swing": round(summary["max_down_swing_at_pct"], 4),
    }


def _day_detail(day_res, pcts, ref_labels):
    """metrics.json detail for one scan day of one ticker."""
    rec = day_res.get("recommended_ref")
    thresholds_pct = {}
    for pct in pcts:
        summaries = day_res["ref_summaries"][pct]
        thresholds_pct[f"{pct:.4f}"] = {
            "pct": pct,
            "references": {lab: _ref_block(summaries[lab])
                           for lab in ref_labels if summaries[lab]["n"] > 0},
        }
    sv = day_res["swing_summaries"]
    swings = {
        lab: {
            "avg_up_swing_pct": round(sv[lab]["avg_up_swing_pct"], 6),
            "avg_down_swing_pct": round(sv[lab]["avg_down_swing_pct"], 6),
            "max_up_swing_pct": round(sv[lab]["max_up_swing_pct"], 6),
            "max_down_swing_pct": round(sv[lab]["max_down_swing_pct"], 6),
            "avg_up_swing": round(sv[lab]["avg_up_swing"], 4),
            "avg_down_swing": round(sv[lab]["avg_down_swing"], 4),
            "max_up_swing": round(sv[lab]["max_up_swing_at_pct"], 4),
            "max_down_swing": round(sv[lab]["max_down_swing_at_pct"], 4),
        }
        for lab in ref_labels if sv[lab]["n"] > 0
    }
    return {
        "n_sessions": day_res["n_days"],
        "n_skipped": day_res["n_skipped"],
        "n_baseline_substituted": day_res.get("n_baseline_substituted", 0),
        "recommended_reference": rec,
        "recommended_reference_deviation": (
            round(day_res["steadiness"].get(rec, 0.0), 4) if rec else None),
        "steadiness": {k: round(v, 4) for k, v in day_res.get("steadiness", {}).items()},
        "thresholds_pct": thresholds_pct,
        "swings": swings,
    }


def build_metrics(all_results, config, source_label):
    """Aggregate the per-ticker / per-day analyzer results into the contract metrics
    dict. Hit rates are nested: tickers_detail[ticker]["by_day"][day]
    ["thresholds_pct"][pct_str]["references"][label]; swings live once per day."""
    tickers = [t for t in all_results if t != "_meta"]
    detail = {}
    recommended = {}
    total_sessions = 0
    for ticker in tickers:
        res = all_results[ticker]
        by_day = {}
        recommended[ticker] = {}
        for day_name in res["days"]:
            day_res = res["by_day"][day_name]
            total_sessions += day_res["n_days"]
            recommended[ticker][day_name] = day_res.get("recommended_ref")
            by_day[day_name] = _day_detail(day_res, res["pcts"], res["ref_labels"])
        detail[ticker] = {
            "pcts": res["pcts"],
            "days": res["days"],
            "by_day": by_day,
        }
    return {
        "status": "ok",
        "strategy": "mon-wed-fri-price-level-touch-percentage",
        "tickers": tickers,
        "pcts": {t: list(all_results[t]["pcts"]) for t in tickers},
        "days": config.scan_days,
        "baseline": "prior trading day 3:50-3:55 PM ET (per-minute) + 3:50-55 average",
        "session": "9:30 AM-4:00 PM ET",
        "lookback_days": config.backtest_days,
        "bar_interval_minutes": config.bar_minutes,
        "target_spend": config.target_spend,   # inert (no premium in this study)
        "outlier_max": config.outlier_max,      # inert (no trade P&L in this study)
        "data_source": source_label,
        "total_sessions_analyzed": total_sessions,
        "recommended_reference_by_ticker_day": recommended,
        "tickers_detail": detail,
    }


def save_artifacts(out_dir, all_results):
    """swings.csv (pipeline-contract ledger) + hit_rates.png (optional chart).

    The engine already wrote touch_summary_*.csv / swings_*.csv / per-ticker TXT
    into out_dir; here we add the fixed-name contract files."""
    import csv

    tickers = [t for t in all_results if t != "_meta"]

    # swings.csv — fixed-name copy of the per-session × per-reference × pct ledger,
    # now carrying the scan day on every row.
    with open(os.path.join(out_dir, "swings.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "day", "base_ref_time", "base_ref_price",
                    "pct", "threshold", "up_level", "down_level",
                    "sess_high", "sess_low",
                    "max_up_swing_pct", "max_down_swing_pct",
                    "max_up_swing", "max_down_swing", "touched_up", "touched_down",
                    "touched_both", "touched_neither"])
        for ticker in tickers:
            res = all_results[ticker]
            for day_name in res["days"]:
                recs = res["by_day"][day_name]["records"]
                for r in sorted(recs, key=lambda x: (x.date, x.ref_label, x.pct)):
                    w.writerow([r.date, r.ticker, r.day, r.ref_label, r.ref_price,
                                f"{r.pct:.4f}", r.threshold, r.up_level, r.down_level,
                                r.sess_high, r.sess_low,
                                f"{r.max_up_swing_pct:.6f}", f"{r.max_down_swing_pct:.6f}",
                                r.max_up_swing, r.max_down_swing,
                                r.touched_up, r.touched_down, r.touched_both,
                                r.touched_neither])

    # hit_rates.png — rows = tickers, columns = scan days. Each cell plots up%/down%
    # touch rate as a function of the percentage threshold (at that day's
    # recommended baseline), so Monday/Wednesday/Friday sit side by side per ticker.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plot_tickers = [t for t in tickers
                        if any(all_results[t]["by_day"][d]["n_days"] >= 3
                               for d in all_results[t]["days"])]
        if plot_tickers:
            days = all_results[plot_tickers[0]]["days"]
            n, ncols = len(plot_tickers), len(days)
            fig, axes = plt.subplots(n, ncols,
                                     figsize=(4.2 * ncols, 2.6 * n), squeeze=False)
            for row, ticker in enumerate(plot_tickers):
                res = all_results[ticker]
                pcts = res["pcts"]
                xlabels = [f"{p:.1%}" for p in pcts]
                x = range(len(pcts))
                for col, day_name in enumerate(days):
                    ax = axes[row][col]
                    day_res = res["by_day"][day_name]
                    rec = day_res.get("recommended_ref")
                    if day_res["n_days"] < 3 or not rec:
                        ax.axis("off")
                        continue
                    ups = [day_res["ref_summaries"][p][rec]["up_rate"] * 100 for p in pcts]
                    dns = [day_res["ref_summaries"][p][rec]["down_rate"] * 100 for p in pcts]
                    ax.bar([i - 0.2 for i in x], ups, width=0.4,
                           label="up hit %", color="#2ca02c")
                    ax.bar([i + 0.2 for i in x], dns, width=0.4,
                           label="down hit %", color="#d62728")
                    ax.set_xticks(list(x))
                    ax.set_xticklabels(xlabels, fontsize=7)
                    if col == 0:
                        ax.set_ylabel(f"{ticker}\nhit %", fontsize=8)
                    ax.set_title(f"{ticker} — {day_name} (@{rec})", fontsize=8)
                    ax.legend(fontsize=6)
            fig.suptitle("Touch rate vs percentage threshold — by ticker and scan day",
                         y=1.0)
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "hit_rates.png"), dpi=110)
            plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics):
    print("\n" + "=" * 66)
    print("  STRATEGY SUMMARY — Mon/Wed/Fri price-level-touch (percentage)")
    print("=" * 66)
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Lookback    : {metrics.get('lookback_days')} days")
    print(f"  Scan days   : {', '.join(metrics.get('days', []))}")
    print(f"  Tickers     : {', '.join(metrics.get('tickers', []))}")
    for ticker, d in metrics.get("tickers_detail", {}).items():
        print(f"  {ticker}:")
        for day_name in d.get("days", []):
            day = d["by_day"][day_name]
            rec = day.get("recommended_reference")
            print(f"    {day_name:>9} ({day['n_sessions']} sessions, best ref {rec}):")
            for pct_str, block in day.get("thresholds_pct", {}).items():
                pct = block.get("pct", float(pct_str))
                rb = block.get("references", {}).get(rec, {}) if rec else {}
                print(f"        ±{pct:>5.2%}: "
                      f"+{rb.get('up_rate', 0)*100:.0f}% / "
                      f"-{rb.get('down_rate', 0)*100:.0f}% "
                      f"(neither {rb.get('neither_rate', 0)*100:.0f}%)")
    print("=" * 66 + "\n")
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
        print("  [data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — falling back "
              "to yfinance for stock bars (still real prices; no options here).")

    try:
        import level_touch_engine as le
        from backtest_level_touch import LOOKBACK_DAYS
        from config import Config

        # Deliver the rich per-ticker TXT + combined CSVs into the results dir too.
        le.RESULTS_DIR = out_dir

        all_results = le.run_level_touch(
            lookback_days=LOOKBACK_DAYS,
            header_extra=(
                "Touch = scan-day session high/low reaches prior-day ref × (1 ± pct) "
                "at 1% / 1.5% / 2% / 2.5% / 3%, for Mon/Wed/Fri; swings shown as % of "
                "reference ($ in brackets)."
            ),
        )

        config = Config()
        config.backtest_days = LOOKBACK_DAYS
        source_label = all_results.get("_meta", {}).get("source_label", "unknown")
        metrics = build_metrics(all_results, config, source_label)
        save_artifacts(out_dir, all_results)
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "mon-wed-fri-price-level-touch-percentage",
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
