#!/usr/bin/env python
"""
PIPELINE ADAPTER for the weekly-move-probability study.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone analysis in backtest_weekly_move.py /
weekly_move_engine.py and emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json       machine-readable metrics  (REQUIRED)
       - weekly_log.csv     per-week (ticker × week) terminal-return ledger
       - probabilities.png  up/down/flat probability bars per ticker (optional)
     plus the rich per-ticker weekly_move_<ticker>_*.txt and the combined
     probability_summary_*.csv / weekly_log_*.csv the standalone run produces
     (RESULTS_DIR is pointed at the same directory).
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The research logic lives in analysis/weekly_move.py + weekly_move_engine.py — this
file only adapts it to the pipeline. Run by hand with
`python backtest_weekly_move.py` for the full terminal report, or
`python strategy.py` to also produce the contract artifacts.

NOTE: this is a stock-price study — there are no options and no P&L, so the
template's target_spend / outlier_max are not applicable and are omitted.
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


def _summary_block(s: dict) -> dict:
    """One scope's (ticker or pooled) stats, rounded for metrics.json."""
    return {
        "weeks": s["n"],
        "up": s["up"], "p_up": round(s["p_up"], 4),
        "down": s["down"], "p_down": round(s["p_down"], 4),
        "flat": s["flat"], "p_flat": round(s["p_flat"], 4),
        "mean_return": round(s["mean_return"], 6),
        "median_return": round(s["median_return"], 6),
        "stdev_return": round(s["stdev_return"], 6),
        "min_return": round(s["min_return"], 6),
        "max_return": round(s["max_return"], 6),
    }


def build_metrics(all_results, config, source_label):
    """Aggregate the per-ticker analyzer results into the contract metrics dict."""
    import weekly_move_engine as we

    tickers = [t for t in all_results if t != "_meta"]
    threshold = config.threshold
    detail = {}
    total_weeks = 0
    for ticker in tickers:
        res = all_results[ticker]
        total_weeks += res["n_weeks"]
        s = we.summarize(res["records"], threshold)
        detail[ticker] = {
            "n_weeks": res["n_weeks"],
            "n_dropped": res["n_dropped"],
            "n_fallback_weeks": res["n_fallback_weeks"],
            "n_thin_weeks": res["n_thin_weeks"],
            "dropped": res["dropped"],
            **_summary_block(s),
        }
    pooled = we.pooled_records(all_results)
    pooled_block = _summary_block(we.summarize(pooled, threshold)) if pooled else {}

    return {
        "status": "ok",
        "strategy": "weekly-move-probability",
        "measurement": "terminal (Friday close-to-next-Friday close)",
        "tickers": tickers,
        "threshold": threshold,
        "reference_window": "3:50-4:00 PM ET (average of minute closes)",
        "holiday_rule": "fall back to prior Thursday (then Wed...) on a Friday holiday",
        "lookback_days": config.backtest_days,
        "bar_interval_minutes": config.bar_minutes,
        "data_source": source_label,
        "total_weeks_analyzed": total_weeks,
        "pooled": pooled_block,
        "tickers_detail": detail,
    }


def save_artifacts(out_dir, all_results, threshold):
    """weekly_log.csv (fixed-name contract ledger) + probabilities.png (chart).

    The engine already wrote probability_summary_*.csv / weekly_log_*.csv /
    per-ticker TXT into out_dir; here we add the fixed-name contract files."""
    import csv
    import weekly_move_engine as we

    tickers = [t for t in all_results if t != "_meta"]

    # weekly_log.csv — fixed-name per-week ledger (all tickers).
    with open(os.path.join(out_dir, "weekly_log.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "entry_date", "entry_ref", "exit_date", "exit_ref",
                    "weekly_return", "weekly_return_pct", "bucket",
                    "entry_ref_date", "exit_ref_date",
                    "entry_fallback", "exit_fallback",
                    "n_entry_bars", "n_exit_bars"])
        for ticker in tickers:
            for r in sorted(all_results[ticker]["records"],
                            key=lambda x: x.entry_date):
                w.writerow([r.ticker, r.entry_date, r.entry_ref,
                            r.exit_date, r.exit_ref,
                            f"{r.weekly_return:.6f}", f"{r.weekly_return:.2%}",
                            r.bucket, r.entry_ref_date, r.exit_ref_date,
                            r.entry_fallback, r.exit_fallback,
                            r.n_entry_bars, r.n_exit_bars])

    # probabilities.png — grouped up/flat/down bars, one cluster per ticker plus
    # a pooled cluster.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        scopes, ups, downs, flats = [], [], [], []
        for ticker in tickers:
            res = all_results[ticker]
            if res["n_weeks"] < we.MIN_SAMPLES:
                continue
            s = we.summarize(res["records"], threshold)
            scopes.append(ticker)
            ups.append(s["p_up"] * 100)
            downs.append(s["p_down"] * 100)
            flats.append(s["p_flat"] * 100)
        pooled = we.pooled_records(all_results)
        if pooled:
            s = we.summarize(pooled, threshold)
            scopes.append("POOLED")
            ups.append(s["p_up"] * 100)
            downs.append(s["p_down"] * 100)
            flats.append(s["p_flat"] * 100)

        if scopes:
            x = range(len(scopes))
            fig, ax = plt.subplots(figsize=(1.6 * len(scopes) + 3, 5))
            ax.bar([i - 0.27 for i in x], ups, width=0.27,
                   label=f"up >= +{threshold:.1%}", color="#2ca02c")
            ax.bar([i for i in x], flats, width=0.27,
                   label=f"flat (within +/-{threshold:.1%})", color="#7f7f7f")
            ax.bar([i + 0.27 for i in x], downs, width=0.27,
                   label=f"down <= -{threshold:.1%}", color="#d62728")
            ax.set_xticks(list(x))
            ax.set_xticklabels(scopes)
            ax.set_ylabel("probability (%)")
            ax.set_title(f"Weekly move probability (Friday->next-Friday, "
                         f"+/-{threshold:.2%} band)")
            ax.legend()
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "probabilities.png"), dpi=110)
            plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics):
    print("\n" + "=" * 60)
    print("  STRATEGY SUMMARY — weekly move probability")
    print("=" * 60)
    thr = metrics.get("threshold", 0.015)
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Lookback    : {metrics.get('lookback_days')} days")
    print(f"  Band        : +/-{thr:.2%}")
    print(f"  Tickers     : {', '.join(metrics.get('tickers', []))}")
    for ticker, d in metrics.get("tickers_detail", {}).items():
        print(f"  {ticker:>6}: {d['n_weeks']:>3} wks   "
              f"up {d['p_up']*100:.0f}%  down {d['p_down']*100:.0f}%  "
              f"flat {d['p_flat']*100:.0f}%")
    p = metrics.get("pooled", {})
    if p:
        print(f"  {'POOLED':>6}: {p['weeks']:>3} wks   "
              f"up {p['p_up']*100:.0f}%  down {p['p_down']*100:.0f}%  "
              f"flat {p['p_flat']*100:.0f}%")
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

    if not os.environ.get("ALPACA_API_KEY") or not (
            os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")):
        print("  [data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — falling back "
              "to yfinance for stock bars (note: yfinance minute history is "
              "limited to ~30 days, so a long lookback needs Alpaca).")

    try:
        import weekly_move_engine as we
        from backtest_weekly_move import LOOKBACK_DAYS, THRESHOLD
        from config import Config

        # Deliver the rich per-ticker TXT + combined CSVs into the results dir too.
        we.RESULTS_DIR = out_dir

        all_results = we.run_weekly_move(
            lookback_days=LOOKBACK_DAYS,
            threshold=THRESHOLD,
            header_extra=(
                "Bucket: up if weekly return >= +threshold, down if <= -threshold, "
                "else flat. Reference = average of 3:50-4:00 PM ET minute closes."
            ),
        )

        config = Config()
        config.backtest_days = LOOKBACK_DAYS
        config.threshold = THRESHOLD
        source_label = all_results.get("_meta", {}).get("source_label", "unknown")
        metrics = build_metrics(all_results, config, source_label)
        save_artifacts(out_dir, all_results, THRESHOLD)
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "weekly-move-probability",
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
