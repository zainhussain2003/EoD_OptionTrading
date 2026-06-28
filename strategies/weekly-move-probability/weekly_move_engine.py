#!/usr/bin/env python3
"""
Engine for the weekly-move-probability study.

Wraps analysis.weekly_move (which builds the per-week Friday→next-Friday terminal
returns) and produces per-ticker stdout tables plus CSV + TXT artifacts in
RESULTS_DIR.

For each ticker, and pooled across all tickers, it reports:
  • P(up ≥ +threshold), P(down ≤ -threshold), P(within ±threshold band),
  • week count, and the mean / median / stdev of the weekly returns.
The three probabilities sum to 100% by construction.

Output files (into RESULTS_DIR):
  weekly_move_<ticker>_<lookback>days_<stamp>.txt   per-ticker report
  probability_summary_<lookback>days_<stamp>.csv    per-ticker + pooled summary
  weekly_log_<lookback>days_<stamp>.csv             per-week ledger (all tickers)
"""
import contextlib
import csv
import io
import os
import statistics
import sys
from datetime import datetime

# Load .env if present (Alpaca credentials)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import Config
from analysis.weekly_move import WeeklyMoveAnalyzer

RESULTS_DIR = "backtest_results"
MIN_SAMPLES = 3            # a ticker needs >= 3 weeks to report a probability


# ── tiny ANSI helpers (no-op when output is piped to a file) ──────────────
def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def green(t):  return _c(t, "32")
def red(t):    return _c(t, "31")
def yellow(t): return _c(t, "33")
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "36")


def get_fetcher():
    """Alpaca if keys present, else yfinance fallback. Stock bars from either are
    REAL market prices."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher
    if ALPACA_AVAILABLE:
        f = AlpacaFetcher.from_env()
        if f is not None:
            return f, "Alpaca Markets API"
    return YFinanceFetcher(), "yfinance (set ALPACA_API_KEY for Alpaca data)"


# ── aggregation ─────────────────────────────────────────────────────────────
def summarize(records: list, threshold: float) -> dict:
    """Probability + return stats over a list of WeeklyMoveRecord."""
    n = len(records)
    up = sum(1 for r in records if r.bucket == "up")
    down = sum(1 for r in records if r.bucket == "down")
    flat = sum(1 for r in records if r.bucket == "flat")
    rets = [r.weekly_return for r in records]
    return {
        "threshold": threshold,
        "n": n,
        "up": up, "down": down, "flat": flat,
        "p_up": (up / n) if n else 0.0,
        "p_down": (down / n) if n else 0.0,
        "p_flat": (flat / n) if n else 0.0,
        "mean_return": (statistics.fmean(rets) if rets else 0.0),
        "median_return": (statistics.median(rets) if rets else 0.0),
        "stdev_return": (statistics.pstdev(rets) if len(rets) >= 1 else 0.0),
        "min_return": (min(rets) if rets else 0.0),
        "max_return": (max(rets) if rets else 0.0),
    }


def pooled_records(all_results: dict) -> list:
    out = []
    for ticker, res in all_results.items():
        if ticker == "_meta":
            continue
        out.extend(res["records"])
    return out


# ── printing ────────────────────────────────────────────────────────────────
def _prob_line(label: str, s: dict) -> str:
    return (f"  {label:>8}: {s['n']:>3} wks   "
            f"up {s['up']:>3} ({s['p_up']:.1%})   "
            f"down {s['down']:>3} ({s['p_down']:.1%})   "
            f"flat {s['flat']:>3} ({s['p_flat']:.1%})   "
            f"| mean {s['mean_return']:+.3%}  med {s['median_return']:+.3%}  "
            f"sd {s['stdev_return']:.3%}")


def print_ticker_block(result: dict):
    ticker = result["ticker"]
    thr = result["threshold"]
    print(bold("═" * 92))
    print(bold(f"  {ticker}  —  Friday→next-Friday weekly move, ±{thr:.2%} band"))
    print(bold("═" * 92))

    if result["n_weeks"] < MIN_SAMPLES:
        print(red(f"  Not enough data for {ticker} "
                  f"({result['n_weeks']} usable weeks).\n"))
        return

    fb = result["n_fallback_weeks"]
    th = result["n_thin_weeks"]
    notes = []
    if fb:
        notes.append(f"{fb} week(s) used a Thursday/earlier fallback leg")
    if th:
        notes.append(f"{th} week(s) had a thin reference window")
    note = ("   (" + "; ".join(notes) + ")") if notes else ""
    print(f"  Weeks analyzed: {result['n_weeks']}   "
          f"dropped (no data): {result['n_dropped']}{note}")
    print()

    s = summarize(result["records"], thr)
    p_up = green(f"{s['p_up']:.2%}")
    p_down = red(f"{s['p_down']:.2%}")
    p_flat = yellow(f"{s['p_flat']:.2%}")
    print(bold("  Probabilities (terminal, close-to-close):"))
    print(f"    P(up   >= +{thr:.2%}) : {p_up}   ({s['up']}/{s['n']})")
    print(f"    P(down <= -{thr:.2%}) : {p_down}   ({s['down']}/{s['n']})")
    print(f"    P(within +/-{thr:.2%}) : {p_flat}   ({s['flat']}/{s['n']})")
    print()
    print(bold("  Weekly return stats:"))
    print(f"    mean {s['mean_return']:+.3%}   median {s['median_return']:+.3%}   "
          f"stdev {s['stdev_return']:.3%}   "
          f"min {s['min_return']:+.2%}   max {s['max_return']:+.2%}")
    print()


def print_overall(all_results: dict, threshold: float):
    print(bold("\n" + "█" * 92))
    print(bold("  SUMMARY — weekly move probability by ticker (and pooled)"))
    print(bold("█" * 92))
    for ticker, res in all_results.items():
        if ticker == "_meta":
            continue
        if res["n_weeks"] < MIN_SAMPLES:
            print(f"  {ticker:>6} : {yellow('insufficient data')}")
            continue
        print(_prob_line(ticker, summarize(res["records"], threshold)))
    pooled = pooled_records(all_results)
    if pooled:
        print(bold("  " + "-" * 88))
        print(bold(_prob_line("POOLED", summarize(pooled, threshold))))
    print()


# ── CSV / TXT artifacts ───────────────────────────────────────────────────────
def save_probability_summary_csv(path, all_results, threshold, lookback_days,
                                 source_label):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# Weekly move probability — summary"])
        w.writerow([f"# Friday→next-Friday terminal return, ±{threshold:.4f} band"])
        w.writerow([f"# Lookback = {lookback_days} calendar days  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        w.writerow([])
        w.writerow(["scope", "threshold", "weeks",
                    "up", "p_up", "down", "p_down", "flat", "p_flat",
                    "mean_return", "median_return", "stdev_return",
                    "min_return", "max_return"])

        def _row(scope, s):
            return [scope, f"{threshold:.4f}", s["n"],
                    s["up"], f"{s['p_up']:.4f}",
                    s["down"], f"{s['p_down']:.4f}",
                    s["flat"], f"{s['p_flat']:.4f}",
                    f"{s['mean_return']:.6f}", f"{s['median_return']:.6f}",
                    f"{s['stdev_return']:.6f}",
                    f"{s['min_return']:.6f}", f"{s['max_return']:.6f}"]

        for ticker, res in all_results.items():
            if ticker == "_meta":
                continue
            w.writerow(_row(ticker, summarize(res["records"], threshold)))
        pooled = pooled_records(all_results)
        if pooled:
            w.writerow(_row("POOLED", summarize(pooled, threshold)))


def save_weekly_log_csv(path, all_results, threshold, lookback_days, source_label):
    """Long/tidy per-week ledger: one row per (ticker × week)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# Weekly move probability — per-week ledger"])
        w.writerow([f"# Friday→next-Friday terminal return, ±{threshold:.4f} band"])
        w.writerow([f"# Lookback = {lookback_days} calendar days  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        w.writerow([])
        w.writerow(["ticker", "entry_date", "entry_ref", "exit_date", "exit_ref",
                    "weekly_return", "weekly_return_pct", "bucket",
                    "entry_ref_date", "exit_ref_date",
                    "entry_fallback", "exit_fallback",
                    "n_entry_bars", "n_exit_bars"])
        for ticker, res in all_results.items():
            if ticker == "_meta":
                continue
            for r in sorted(res["records"], key=lambda x: x.entry_date):
                w.writerow([r.ticker, r.entry_date, r.entry_ref,
                            r.exit_date, r.exit_ref,
                            f"{r.weekly_return:.6f}", f"{r.weekly_return:.2%}",
                            r.bucket, r.entry_ref_date, r.exit_ref_date,
                            r.entry_fallback, r.exit_fallback,
                            r.n_entry_bars, r.n_exit_bars])


def save_ticker_txt(path, result, threshold, lookback_days, source_label):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_ticker_block(result)
        # Per-week detail under the summary.
        if result["n_weeks"] >= MIN_SAMPLES:
            print("  Per-week log:")
            print(f"  {'entry':>10} {'exit':>10} {'entry_ref':>10} {'exit_ref':>10} "
                  f"{'return':>9}  {'bucket':>5}  flags")
            for r in sorted(result["records"], key=lambda x: x.entry_date):
                flags = []
                if r.entry_fallback:
                    flags.append("entry-fallback")
                if r.exit_fallback:
                    flags.append("exit-fallback")
                print(f"  {r.entry_date:>10} {r.exit_date:>10} "
                      f"{r.entry_ref:>10.2f} {r.exit_ref:>10.2f} "
                      f"{r.weekly_return:>+9.2%}  {r.bucket:>5}  "
                      f"{','.join(flags)}")
            if result["dropped"]:
                print("\n  Dropped weeks (never silently filled):")
                for d in result["dropped"]:
                    print(f"    - {d}")
    hdr = (f"WEEKLY MOVE PROBABILITY — {result['ticker']} (±{threshold:.2%} band)\n"
           f"Friday→next-Friday terminal (close-to-close) return\n"
           f"Reference = average of 3:50–4:00 PM ET minute closes (Thursday "
           f"fallback on Friday holidays)\n"
           f"Lookback = {lookback_days} calendar days\n"
           f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
           + "=" * 92 + "\n\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(hdr)
        fh.write(buf.getvalue())


# ── driver ────────────────────────────────────────────────────────────────────
def run_weekly_move(lookback_days=None, threshold=None, header_extra=""):
    """Fetch Friday references per ticker, compute weekly-move buckets, print and
    save results. Returns {ticker: result, '_meta': {...}}."""
    config = Config()
    if lookback_days is not None:
        config.backtest_days = lookback_days
    if threshold is not None:
        config.threshold = threshold
    lookback_days = config.backtest_days
    threshold = config.threshold

    print(bold("\n" + "═" * 92))
    print(bold("  WEEKLY MOVE PROBABILITY ANALYSIS"))
    print(bold(f"  Lookback window : {lookback_days} calendar days"))
    print(bold(f"  Band            : ±{threshold:.2%} (up / down / flat)"))
    print(bold("  Reference       : avg of 3:50–4:00 PM ET minute closes "
               "(Thursday fallback on Friday holidays)"))
    print(bold("  Measurement     : terminal Friday→next-Friday close-to-close"))
    if header_extra:
        print(f"  {header_extra}")
    print(bold("═" * 92))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    print(f"  Tickers: {', '.join(config.tickers)}")
    print()

    analyzer = WeeklyMoveAnalyzer(fetcher, config)
    raw = analyzer.run(list(config.tickers))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    all_results = {}
    for ticker in config.tickers:
        res = raw[ticker]
        all_results[ticker] = res

        print(bold("\n" + "█" * 92))
        print_ticker_block(res)

        txt_path = os.path.join(
            RESULTS_DIR,
            f"weekly_move_{ticker.lower()}_{lookback_days}days_{stamp}.txt")
        save_ticker_txt(txt_path, res, threshold, lookback_days, source_label)
        print(bold("─" * 92))
        print(f"  {cyan('Saved TXT:')} {bold(txt_path)}")
        print(bold("─" * 92))

    print_overall(all_results, threshold)

    summary_csv = os.path.join(
        RESULTS_DIR, f"probability_summary_{lookback_days}days_{stamp}.csv")
    log_csv = os.path.join(
        RESULTS_DIR, f"weekly_log_{lookback_days}days_{stamp}.csv")
    save_probability_summary_csv(summary_csv, all_results, threshold,
                                 lookback_days, source_label)
    save_weekly_log_csv(log_csv, all_results, threshold, lookback_days, source_label)
    print(f"  {cyan('Saved CSV:')} {bold(summary_csv)}")
    print(f"  {cyan('Saved CSV:')} {bold(log_csv)}")
    print()

    all_results["_meta"] = {"source_label": source_label,
                            "lookback_days": lookback_days,
                            "threshold": threshold, "stamp": stamp}
    return all_results
