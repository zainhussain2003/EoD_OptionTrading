#!/usr/bin/env python3
"""
Engine for the Friday price-level-touch study.

Wraps analysis.level_touch (which builds the per-Friday touch/swing records) and
produces the same kind of output the time-frame study does: bold-bordered
per-ticker tables printed to stdout, plus CSV + TXT artifacts saved to RESULTS_DIR.

For each ticker it reports, per Thursday reference time (3:50–3:55 PM plus the
3:50–55 average):
  • Fridays analyzed, +threshold hits, -threshold hits, both, neither (+ %),
  • average and largest max-up / max-down swing from that baseline,
and then ranks the reference minutes by how steady a baseline each one is
(lowest average deviation from the per-Friday 6-minute mean) and recommends one.

Output files (into RESULTS_DIR):
  level_touch_<ticker>_<lookback>days_<stamp>.txt   per-ticker report
  touch_summary_<lookback>days_<stamp>.csv          combined hit-rate table
  swings_<lookback>days_<stamp>.csv                 per-Friday × per-reference ledger
"""
import contextlib
import csv
import io
import os
import sys
from datetime import datetime

# Load .env if present (Alpaca credentials)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import Config
from analysis.level_touch import LevelTouchAnalyzer, AVG_LABEL

RESULTS_DIR = "backtest_results"
MIN_SAMPLES = 3            # a reference needs >= 3 Fridays to report a hit rate


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
    REAL market prices (the Black-Scholes path only ever applied to options)."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher
    if ALPACA_AVAILABLE:
        f = AlpacaFetcher.from_env()
        if f is not None:
            return f, "Alpaca Markets API"
    return YFinanceFetcher(), "yfinance (set ALPACA_API_KEY for Alpaca data)"


# ── aggregation ───────────────────────────────────────────────────────────────
def _pct(num, den):
    return (num / den) if den else 0.0


def summarize_ref(records: list) -> dict:
    """Hit-rate + swing stats over one reference label's per-Friday records."""
    n = len(records)
    up = sum(1 for r in records if r.touched_up)
    down = sum(1 for r in records if r.touched_down)
    both = sum(1 for r in records if r.touched_both)
    neither = sum(1 for r in records if r.touched_neither)
    ups = [r.max_up_swing for r in records]
    downs = [r.max_down_swing for r in records]
    return {
        "n": n,
        "up_hits": up, "up_rate": _pct(up, n),
        "down_hits": down, "down_rate": _pct(down, n),
        "both": both, "both_rate": _pct(both, n),
        "neither": neither, "neither_rate": _pct(neither, n),
        "avg_up_swing": (sum(ups) / n) if n else 0.0,
        "avg_down_swing": (sum(downs) / n) if n else 0.0,
        "max_up_swing": max(ups) if ups else 0.0,
        "max_down_swing": max(downs) if downs else 0.0,
    }


def compute_steadiness(per_friday_refs: dict, single_labels: list) -> dict:
    """Average absolute deviation of each single-minute reference price from that
    Friday's mean of the six reference prices. Lower = steadier baseline."""
    sums = {lab: 0.0 for lab in single_labels}
    counts = {lab: 0 for lab in single_labels}
    for refs in per_friday_refs.values():
        present = {lab: refs[lab] for lab in single_labels if lab in refs}
        if len(present) < 2:
            continue
        mean = sum(present.values()) / len(present)
        for lab, price in present.items():
            sums[lab] += abs(price - mean)
            counts[lab] += 1
    return {lab: (sums[lab] / counts[lab]) for lab in single_labels if counts[lab]}


def analyze_results(result: dict) -> dict:
    """Attach per-reference summaries, steadiness ranking, and the recommended
    reference minute to a raw analyzer result."""
    by_label = {lab: [] for lab in result["ref_labels"]}
    for r in result["records"]:
        by_label.setdefault(r.thu_ref_label, []).append(r)
    ref_summaries = {lab: summarize_ref(by_label.get(lab, []))
                     for lab in result["ref_labels"]}
    steadiness = compute_steadiness(result["per_friday_refs"], result["single_labels"])
    recommended = min(steadiness, key=steadiness.get) if steadiness else None
    result["ref_summaries"] = ref_summaries
    result["steadiness"] = steadiness
    result["recommended_ref"] = recommended
    return result


# ── printing ──────────────────────────────────────────────────────────────────
def print_ticker_block(result: dict):
    ticker = result["ticker"]
    thr = result["threshold"]
    print(bold("═" * 86))
    print(bold(f"  {ticker}  —  level threshold ±${thr:.2f}"
               f"     (Thursday close baseline → Friday touch)"))
    print(bold("═" * 86))

    if result["n_fridays"] < MIN_SAMPLES:
        print(red(f"  Not enough data captured for {ticker} "
                  f"({result['n_fridays']} usable Fridays).\n"))
        return

    sub = result.get("n_baseline_substituted", 0)
    note = (f"   ({sub} week(s) used a pre-Thursday baseline — Thu holiday)"
            if sub else "")
    print(f"  Fridays analyzed: {result['n_fridays']}   "
          f"skipped (no data): {result['n_skipped']}{note}")
    print()

    # Hit-rate table
    print(f"  {'Thu ref':>11} {'Fridays':>8}   {'+$'+format(thr,'.0f')+' hit':>14}   "
          f"{'-$'+format(thr,'.0f')+' hit':>14}   {'Both':>13}   {'Neither':>13}")
    print(f"  {'-'*11} {'-'*8}   {'-'*14}   {'-'*14}   {'-'*13}   {'-'*13}")
    rec = result.get("recommended_ref")
    for lab in result["ref_labels"]:
        s = result["ref_summaries"][lab]
        if s["n"] == 0:
            continue
        marker = cyan(" ◀") if lab == rec else "  "
        up = f"{s['up_hits']} ({s['up_rate']:.1%})"
        dn = f"{s['down_hits']} ({s['down_rate']:.1%})"
        bo = f"{s['both']} ({s['both_rate']:.1%})"
        ne = f"{s['neither']} ({s['neither_rate']:.1%})"
        line = (f"  {lab:>11} {s['n']:>8}   {up:>14}   {dn:>14}   "
                f"{bo:>13}   {ne:>13}")
        print((cyan(line) if lab == rec else line) + marker)
    print()

    # Swing stats table
    print(f"  {'Thu ref':>11}   {'avg up swing':>13}  {'avg down swing':>15}  "
          f"{'max up swing':>13}  {'max down swing':>15}")
    print(f"  {'-'*11}   {'-'*13}  {'-'*15}  {'-'*13}  {'-'*15}")
    for lab in result["ref_labels"]:
        s = result["ref_summaries"][lab]
        if s["n"] == 0:
            continue
        print(f"  {lab:>11}   {'+$'+format(s['avg_up_swing'],'.2f'):>13}  "
              f"{'-$'+format(s['avg_down_swing'],'.2f'):>15}  "
              f"{'+$'+format(s['max_up_swing'],'.2f'):>13}  "
              f"{'-$'+format(s['max_down_swing'],'.2f'):>15}")
    print()

    print_steadiness(result)


def print_steadiness(result: dict):
    steadiness = result.get("steadiness") or {}
    rec = result.get("recommended_ref")
    if not steadiness:
        return
    ordered = sorted(steadiness.items(), key=lambda kv: kv[1])
    print(f"  {bold('Steadiest baseline')}  (avg |deviation from the 3:50–55 mean|, "
          f"lower = steadier):")
    parts = []
    for lab, dev in ordered:
        tag = cyan(f"{lab} ${dev:.3f} ◀") if lab == rec else f"{lab} ${dev:.3f}"
        parts.append(tag)
    print("    " + "    ".join(parts))
    print(f"  → {bold('Recommended Thursday reference for ' + result['ticker'])}: "
          f"{green(rec)}\n")


def print_overall(all_results: dict):
    print(bold("\n" + "█" * 86))
    print(bold("  RECOMMENDED THURSDAY REFERENCE — by ticker (steadiest baseline)"))
    print(bold("█" * 86))
    for ticker, res in all_results.items():
        rec = res.get("recommended_ref")
        if rec is None:
            print(f"  {ticker:>6} : {yellow('insufficient data')}")
            continue
        dev = res["steadiness"].get(rec, 0.0)
        print(f"  {ticker:>6} : {green(rec)}   (avg deviation ${dev:.3f}, "
              f"{res['n_fridays']} Fridays)")
    print()


# ── CSV / TXT artifacts ───────────────────────────────────────────────────────
def save_touch_summary_csv(path, all_results, lookback_days, source_label):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# Friday price-level-touch — touch summary"])
        w.writerow([f"# Lookback = {lookback_days} calendar days  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        w.writerow([])
        w.writerow(["ticker", "threshold", "thu_ref", "fridays",
                    "up_hits", "up_rate", "down_hits", "down_rate",
                    "both_hits", "both_rate", "neither_hits", "neither_rate",
                    "avg_up_swing", "avg_down_swing", "max_up_swing",
                    "max_down_swing", "recommended_baseline"])
        for ticker, res in all_results.items():
            rec = res.get("recommended_ref")
            for lab in res["ref_labels"]:
                s = res["ref_summaries"][lab]
                if s["n"] == 0:
                    continue
                w.writerow([
                    ticker, f"{res['threshold']:.2f}", lab, s["n"],
                    s["up_hits"], f"{s['up_rate']:.4f}",
                    s["down_hits"], f"{s['down_rate']:.4f}",
                    s["both"], f"{s['both_rate']:.4f}",
                    s["neither"], f"{s['neither_rate']:.4f}",
                    round(s["avg_up_swing"], 4), round(s["avg_down_swing"], 4),
                    round(s["max_up_swing"], 4), round(s["max_down_swing"], 4),
                    "YES" if lab == rec else ""])


def save_swings_csv(path, all_results, lookback_days, source_label):
    """Long/tidy per-Friday ledger: one row per (Friday × reference)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# Friday price-level-touch — per-Friday swing ledger"])
        w.writerow([f"# Lookback = {lookback_days} calendar days  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        w.writerow([])
        w.writerow(["date", "ticker", "thu_ref_time", "thu_ref_price", "threshold",
                    "up_level", "down_level", "fri_high", "fri_low",
                    "max_up_swing", "max_down_swing", "touched_up", "touched_down",
                    "touched_both", "touched_neither"])
        for ticker, res in all_results.items():
            for r in sorted(res["records"], key=lambda x: (x.date, x.thu_ref_label)):
                w.writerow([r.date, r.ticker, r.thu_ref_label, r.thu_ref_price,
                            r.threshold, r.up_level, r.down_level, r.fri_high,
                            r.fri_low, r.max_up_swing, r.max_down_swing,
                            r.touched_up, r.touched_down, r.touched_both,
                            r.touched_neither])


def save_ticker_txt(path, result, lookback_days, source_label):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_ticker_block(result)
    hdr = (f"FRIDAY PRICE-LEVEL-TOUCH — {result['ticker']} "
           f"(threshold ±${result['threshold']:.2f})\n"
           f"Lookback = {lookback_days} calendar days\n"
           f"Friday scan = 9:30 AM–4:00 PM ET, 1-minute bars\n"
           f"Thursday baseline = 3:50–3:55 PM ET (per-minute) + 3:50–55 average\n"
           f"Touch = Friday session high/low reaches Thursday ref ± threshold\n"
           f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
           + "=" * 86 + "\n\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(hdr)
        fh.write(buf.getvalue())


# ── driver ────────────────────────────────────────────────────────────────────
def run_level_touch(lookback_days=None, header_extra=""):
    """Capture Thursday baselines + Friday sessions per ticker, compute touch /
    swing stats, print and save results. Returns {ticker: analyzed result}."""
    config = Config()
    if lookback_days is not None:
        config.backtest_days = lookback_days
    lookback_days = config.backtest_days

    print(bold("\n" + "═" * 86))
    print(bold("  FRIDAY PRICE-LEVEL-TOUCH ANALYSIS"))
    print(bold(f"  Lookback window: {lookback_days} calendar days"))
    print(bold("  Friday scan    : 9:30 AM–4:00 PM ET, 1-minute bars"))
    print(bold("  Thu baseline   : 3:50–3:55 PM ET (per-minute) + 3:50–55 average"))
    if header_extra:
        print(f"  {header_extra}")
    print(bold("═" * 86))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    thr = config.ticker_thresholds
    print("  Tickers / thresholds: "
          + "   ".join(f"{t} ±${v:.0f}" for t, v in thr.items()))
    print()

    analyzer = LevelTouchAnalyzer(fetcher, config)
    raw = analyzer.run(list(thr.keys()))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    all_results = {}
    for ticker in thr.keys():
        res = analyze_results(raw[ticker])
        all_results[ticker] = res

        print(bold("\n" + "█" * 86))
        print_ticker_block(res)

        txt_path = os.path.join(
            RESULTS_DIR,
            f"level_touch_{ticker.lower()}_{lookback_days}days_{stamp}.txt")
        save_ticker_txt(txt_path, res, lookback_days, source_label)
        print(bold("─" * 86))
        print(f"  {cyan('Saved TXT:')} {bold(txt_path)}")
        print(bold("─" * 86))

    print_overall(all_results)

    summary_csv = os.path.join(
        RESULTS_DIR, f"touch_summary_{lookback_days}days_{stamp}.csv")
    swings_csv = os.path.join(
        RESULTS_DIR, f"swings_{lookback_days}days_{stamp}.csv")
    save_touch_summary_csv(summary_csv, all_results, lookback_days, source_label)
    save_swings_csv(swings_csv, all_results, lookback_days, source_label)
    print(f"  {cyan('Saved CSV:')} {bold(summary_csv)}")
    print(f"  {cyan('Saved CSV:')} {bold(swings_csv)}")
    print()

    all_results["_meta"] = {"source_label": source_label,
                            "lookback_days": lookback_days, "stamp": stamp}
    return all_results
