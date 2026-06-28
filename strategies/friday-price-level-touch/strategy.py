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
    """One reference label's stats, rounded for metrics.json."""
    return {
        "fridays": summary["n"],
        "up_hits": summary["up_hits"], "up_rate": round(summary["up_rate"], 4),
        "down_hits": summary["down_hits"], "down_rate": round(summary["down_rate"], 4),
        "both_hits": summary["both"], "both_rate": round(summary["both_rate"], 4),
        "neither_hits": summary["neither"],
        "neither_rate": round(summary["neither_rate"], 4),
        "avg_up_swing": round(summary["avg_up_swing"], 4),
        "avg_down_swing": round(summary["avg_down_swing"], 4),
        "max_up_swing": round(summary["max_up_swing"], 4),
        "max_down_swing": round(summary["max_down_swing"], 4),
    }


def build_metrics(all_results, config, source_label):
    """Aggregate the per-ticker analyzer results into the contract metrics dict."""
    tickers = [t for t in all_results if t != "_meta"]
    detail = {}
    recommended = {}
    total_fridays = 0
    for ticker in tickers:
        res = all_results[ticker]
        total_fridays += res["n_fridays"]
        rec = res.get("recommended_ref")
        recommended[ticker] = rec
        detail[ticker] = {
            "threshold": res["threshold"],
            "n_fridays": res["n_fridays"],
            "n_skipped": res["n_skipped"],
            "n_baseline_substituted": res.get("n_baseline_substituted", 0),
            "recommended_reference": rec,
            "recommended_reference_deviation": (
                round(res["steadiness"].get(rec, 0.0), 4) if rec else None),
            "steadiness": {k: round(v, 4) for k, v in res.get("steadiness", {}).items()},
            "references": {lab: _ref_block(res["ref_summaries"][lab])
                           for lab in res["ref_labels"]
                           if res["ref_summaries"][lab]["n"] > 0},
        }
    return {
        "status": "ok",
        "strategy": "friday-price-level-touch",
        "tickers": tickers,
        "thresholds": dict(config.ticker_thresholds),
        "day": "Friday",
        "session": "9:30 AM-4:00 PM ET",
        "thursday_reference": "3:50-3:55 PM ET (per-minute) + 3:50-55 average",
        "lookback_days": config.backtest_days,
        "bar_interval_minutes": config.bar_minutes,
        "target_spend": config.target_spend,   # inert (no premium in this study)
        "outlier_max": config.outlier_max,      # inert (no trade P&L in this study)
        "data_source": source_label,
        "total_fridays_analyzed": total_fridays,
        "recommended_reference_by_ticker": recommended,
        "tickers_detail": detail,
    }


def save_artifacts(out_dir, all_results):
    """swings.csv (pipeline-contract ledger) + hit_rates.png (optional chart).

    The engine already wrote touch_summary_*.csv / swings_*.csv / per-ticker TXT
    into out_dir; here we add the fixed-name contract files."""
    import csv

    tickers = [t for t in all_results if t != "_meta"]

    # swings.csv — fixed-name copy of the per-Friday × per-reference ledger.
    with open(os.path.join(out_dir, "swings.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "thu_ref_time", "thu_ref_price", "threshold",
                    "up_level", "down_level", "fri_high", "fri_low",
                    "max_up_swing", "max_down_swing", "touched_up", "touched_down",
                    "touched_both", "touched_neither"])
        for ticker in tickers:
            for r in sorted(all_results[ticker]["records"],
                            key=lambda x: (x.date, x.thu_ref_label)):
                w.writerow([r.date, r.ticker, r.thu_ref_label, r.thu_ref_price,
                            r.threshold, r.up_level, r.down_level, r.fri_high,
                            r.fri_low, r.max_up_swing, r.max_down_swing,
                            r.touched_up, r.touched_down, r.touched_both,
                            r.touched_neither])

    # hit_rates.png — +/- touch rate per reference, one subplot per ticker.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plot_tickers = [t for t in tickers if all_results[t]["n_fridays"] >= 3]
        if plot_tickers:
            n = len(plot_tickers)
            fig, axes = plt.subplots(n, 1, figsize=(10, 2.6 * n), squeeze=False)
            for ax, ticker in zip(axes[:, 0], plot_tickers):
                res = all_results[ticker]
                labels = [lab for lab in res["ref_labels"]
                          if res["ref_summaries"][lab]["n"] > 0]
                ups = [res["ref_summaries"][l]["up_rate"] * 100 for l in labels]
                dns = [res["ref_summaries"][l]["down_rate"] * 100 for l in labels]
                x = range(len(labels))
                ax.bar([i - 0.2 for i in x], ups, width=0.4,
                       label=f"+${res['threshold']:.0f} hit %", color="#2ca02c")
                ax.bar([i + 0.2 for i in x], dns, width=0.4,
                       label=f"-${res['threshold']:.0f} hit %", color="#d62728")
                ax.set_xticks(list(x))
                ax.set_xticklabels(labels, fontsize=8)
                ax.set_ylabel("hit %")
                ax.set_title(f"{ticker}  (±${res['threshold']:.0f})", fontsize=10)
                ax.legend(fontsize=8)
            fig.suptitle("Friday touch rate by Thursday reference time", y=1.0)
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "hit_rates.png"), dpi=110)
            plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics):
    print("\n" + "=" * 60)
    print("  STRATEGY SUMMARY — Friday price-level-touch")
    print("=" * 60)
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Lookback    : {metrics.get('lookback_days')} days")
    print(f"  Tickers     : {', '.join(metrics.get('tickers', []))}")
    for ticker, d in metrics.get("tickers_detail", {}).items():
        rec = d.get("recommended_reference")
        refs = d.get("references", {})
        rb = refs.get(rec, {}) if rec else {}
        thr = d.get("threshold")
        print(f"  {ticker:>6} ±${thr:<5.0f}: {d['n_fridays']} Fridays   "
              f"best ref {rec}   "
              f"+{rb.get('up_rate', 0)*100:.0f}% / -{rb.get('down_rate', 0)*100:.0f}% "
              f"(both {rb.get('both_rate', 0)*100:.0f}%, "
              f"neither {rb.get('neither_rate', 0)*100:.0f}%)")
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
                "Touch = Friday session high/low reaches Thursday ref ± per-ticker "
                "threshold; swings measured from each Thursday baseline."
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
        metrics = {"status": "error", "strategy": "friday-price-level-touch",
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
