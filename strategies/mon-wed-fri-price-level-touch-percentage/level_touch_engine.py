#!/usr/bin/env python3
"""
Engine for the Mon/Wed/Fri price-level-touch (percentage) study.

Wraps analysis.level_touch (which builds the per-scan-day touch/swing records) and
produces bold-bordered per-ticker tables printed to stdout, plus CSV + TXT
artifacts saved to RESULTS_DIR.

For each ticker it reports, for each scan day (Monday, Wednesday, Friday) and per
baseline reference time (3:50–3:55 PM on the prior trading day plus the 3:50–55
average):
  • scan days analyzed, +pct hits, -pct hits, both, neither (+ %),
  • average and largest max-up / max-down swing from that baseline,
and then ranks the reference minutes by steadiness and recommends one. Finally it
prints a combined per-ticker DAY COMPARISON putting the Monday / Wednesday / Friday
averages side by side so they are easy to read together.

Output files (into RESULTS_DIR):
  level_touch_<ticker>_<lookback>days_<stamp>.txt   per-ticker report (all days)
  touch_summary_<lookback>days_<stamp>.csv          combined hit-rate table
  swings_<lookback>days_<stamp>.csv                 per-session × per-reference ledger
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
MIN_SAMPLES = 3            # a day needs >= 3 sessions to report a hit rate


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
    """Hit-rate + swing stats over one reference label's per-session records.

    Swings are reported both as a percentage of the reference price (the primary
    figure for this study) and in dollars (carried in brackets)."""
    n = len(records)
    up = sum(1 for r in records if r.touched_up)
    down = sum(1 for r in records if r.touched_down)
    both = sum(1 for r in records if r.touched_both)
    neither = sum(1 for r in records if r.touched_neither)
    ups = [r.max_up_swing for r in records]
    downs = [r.max_down_swing for r in records]
    ups_pct = [r.max_up_swing_pct for r in records]
    downs_pct = [r.max_down_swing_pct for r in records]
    # The largest single-day percentage swing in each direction, with the matching
    # dollar move from the same session alongside it.
    max_up_i = max(range(n), key=lambda i: ups_pct[i]) if n else None
    max_down_i = max(range(n), key=lambda i: downs_pct[i]) if n else None
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
        "avg_up_swing_pct": (sum(ups_pct) / n) if n else 0.0,
        "avg_down_swing_pct": (sum(downs_pct) / n) if n else 0.0,
        # Biggest single-day % swing each way, paired with that day's $ move.
        "max_up_swing_pct": ups_pct[max_up_i] if n else 0.0,
        "max_up_swing_at_pct": ups[max_up_i] if n else 0.0,
        "max_down_swing_pct": downs_pct[max_down_i] if n else 0.0,
        "max_down_swing_at_pct": downs[max_down_i] if n else 0.0,
    }


def compute_steadiness(per_session_refs: dict, single_labels: list) -> dict:
    """Average absolute deviation of each single-minute reference price from that
    session's mean of the six reference prices. Lower = steadier baseline."""
    sums = {lab: 0.0 for lab in single_labels}
    counts = {lab: 0 for lab in single_labels}
    for refs in per_session_refs.values():
        present = {lab: refs[lab] for lab in single_labels if lab in refs}
        if len(present) < 2:
            continue
        mean = sum(present.values()) / len(present)
        for lab, price in present.items():
            sums[lab] += abs(price - mean)
            counts[lab] += 1
    return {lab: (sums[lab] / counts[lab]) for lab in single_labels if counts[lab]}


def analyze_day_result(day_res: dict, pcts: list, ref_labels: list,
                       single_labels: list) -> dict:
    """Attach per-percentage / per-reference summaries, steadiness ranking, and the
    recommended reference minute to one day's raw analyzer sub-result.

    ref_summaries is nested as {pct: {ref_label: summary}}. The swing figures are
    identical across pcts, so a flat swing_summaries[ref_label] view is also
    provided for the swing table and CSVs."""
    by_pct_label = {p: {lab: [] for lab in ref_labels} for p in pcts}
    for r in day_res["records"]:
        by_pct_label.setdefault(r.pct, {}).setdefault(r.ref_label, []).append(r)
    ref_summaries = {
        p: {lab: summarize_ref(by_pct_label.get(p, {}).get(lab, []))
            for lab in ref_labels}
        for p in pcts
    }
    swing_summaries = ref_summaries[pcts[0]] if pcts else {}
    steadiness = compute_steadiness(day_res["per_session_refs"], single_labels)
    recommended = min(steadiness, key=steadiness.get) if steadiness else None
    day_res["ref_summaries"] = ref_summaries
    day_res["swing_summaries"] = swing_summaries
    day_res["steadiness"] = steadiness
    day_res["recommended_ref"] = recommended
    return day_res


def analyze_ticker(result: dict) -> dict:
    """Run analyze_day_result over each scan day of a ticker's raw result."""
    for day_name in result["days"]:
        analyze_day_result(result["by_day"][day_name], result["pcts"],
                           result["ref_labels"], result["single_labels"])
    return result


# ── printing ──────────────────────────────────────────────────────────────────
def _swing_cell(pct_val: float, dollar_val: float, sign: str) -> str:
    """Percentage swing as the primary figure with the dollar move in brackets,
    e.g. '+2.34% ($8.96)'."""
    return f"{sign}{pct_val:.2%} (${dollar_val:.2f})"


def print_hit_rate_table(day_res: dict, ref_labels: list, pct: float):
    """One hit-rate sub-table for a single percentage threshold within a day."""
    summaries = day_res["ref_summaries"][pct]
    rec = day_res.get("recommended_ref")
    pos = f"+{pct:.1%} hit"
    neg = f"-{pct:.1%} hit"
    print(bold(f"     ── ±{pct:.2%} level ──"))
    print(f"     {'base ref':>11} {'sessions':>8}   {pos:>14}   "
          f"{neg:>14}   {'Both':>13}   {'Neither':>13}")
    print(f"     {'-'*11} {'-'*8}   {'-'*14}   {'-'*14}   {'-'*13}   {'-'*13}")
    for lab in ref_labels:
        s = summaries[lab]
        if s["n"] == 0:
            continue
        marker = cyan(" ◀") if lab == rec else "  "
        up = f"{s['up_hits']} ({s['up_rate']:.1%})"
        dn = f"{s['down_hits']} ({s['down_rate']:.1%})"
        bo = f"{s['both']} ({s['both_rate']:.1%})"
        ne = f"{s['neither']} ({s['neither_rate']:.1%})"
        line = (f"     {lab:>11} {s['n']:>8}   {up:>14}   {dn:>14}   "
                f"{bo:>13}   {ne:>13}")
        print((cyan(line) if lab == rec else line) + marker)
    print()


# Baseline note: which prior trading day each scan day references.
_BASELINE_DAY = {'Monday': 'prior Friday', 'Tuesday': 'prior Monday',
                 'Wednesday': 'prior Tuesday', 'Thursday': 'prior Wednesday',
                 'Friday': 'prior Thursday'}


def print_day_block(result: dict, day_name: str):
    """All five per-pct hit-rate sub-tables + the swing table for one scan day."""
    day_res = result["by_day"][day_name]
    pcts = result["pcts"]
    ref_labels = result["ref_labels"]
    base = _BASELINE_DAY.get(day_name, "prior trading day")

    print(bold(f"  ──────── {day_name.upper()}  "
               f"(baseline = {base} 3:50–55 PM) ────────"))
    if day_res["n_days"] < MIN_SAMPLES:
        print(red(f"     Not enough {day_name} sessions captured "
                  f"({day_res['n_days']}).\n"))
        return

    sub = day_res.get("n_baseline_substituted", 0)
    note = (f"   ({sub} week(s) used an earlier baseline — holiday)" if sub else "")
    print(f"     {day_name}s analyzed: {day_res['n_days']}   "
          f"skipped (no data): {day_res['n_skipped']}{note}")
    print()

    for pct in pcts:
        print_hit_rate_table(day_res, ref_labels, pct)

    # Swing table (same across thresholds; % of reference, $ in brackets).
    print(bold("     ── swings (same for all thresholds; % of reference, $ in "
               "brackets) ──"))
    print(f"     {'base ref':>11}   {'avg up swing':>17}  {'avg down swing':>17}  "
          f"{'max up swing':>17}  {'max down swing':>17}")
    print(f"     {'-'*11}   {'-'*17}  {'-'*17}  {'-'*17}  {'-'*17}")
    sw = day_res["swing_summaries"]
    for lab in ref_labels:
        s = sw[lab]
        if s["n"] == 0:
            continue
        print(f"     {lab:>11}   "
              f"{_swing_cell(s['avg_up_swing_pct'], s['avg_up_swing'], '+'):>17}  "
              f"{_swing_cell(s['avg_down_swing_pct'], s['avg_down_swing'], '-'):>17}  "
              f"{_swing_cell(s['max_up_swing_pct'], s['max_up_swing_at_pct'], '+'):>17}  "
              f"{_swing_cell(s['max_down_swing_pct'], s['max_down_swing_at_pct'], '-'):>17}")
    print()
    print_steadiness(day_res, day_name)


def print_steadiness(day_res: dict, day_name: str):
    steadiness = day_res.get("steadiness") or {}
    rec = day_res.get("recommended_ref")
    if not steadiness:
        return
    ordered = sorted(steadiness.items(), key=lambda kv: kv[1])
    print(f"     {bold('Steadiest baseline')}  (avg |dev from 3:50–55 mean|, "
          f"lower = steadier):")
    parts = []
    for lab, dev in ordered:
        tag = cyan(f"{lab} ${dev:.3f} ◀") if lab == rec else f"{lab} ${dev:.3f}"
        parts.append(tag)
    print("       " + "    ".join(parts))
    print(f"     → {bold('Recommended ' + day_name + ' baseline')}: {green(rec)}\n")


def print_day_comparison(result: dict):
    """The combined per-ticker averages: Monday / Wednesday / Friday side by side,
    each at its own recommended baseline. This is the 'all the averages together'
    view that makes the days easy to read against each other."""
    days = result["days"]
    pcts = result["pcts"]

    print(bold("  ░░ DAY COMPARISON — up% / down% / neither% at each day's "
               "recommended baseline ░░"))
    header = f"  {'pct':>7}  " + "  ".join(f"{d:^24}" for d in days)
    print(bold(header))
    print(f"  {'-'*7}  " + "  ".join("-" * 24 for _ in days))

    def cell(day_res, pct):
        if day_res["n_days"] < MIN_SAMPLES or not day_res.get("recommended_ref"):
            return f"{'n/a':^24}"
        s = day_res["ref_summaries"][pct][day_res["recommended_ref"]]
        return f"{s['up_rate']:.0%} / {s['down_rate']:.0%} / {s['neither_rate']:.0%}".center(24)

    for pct in pcts:
        row = f"  {pct:>6.1%}  " + "  ".join(
            cell(result["by_day"][d], pct) for d in days)
        print(row)

    # Average swing (threshold-independent) per day, at the recommended baseline.
    def swing_cell(day_res):
        if day_res["n_days"] < MIN_SAMPLES or not day_res.get("recommended_ref"):
            return f"{'n/a':^24}"
        s = day_res["swing_summaries"][day_res["recommended_ref"]]
        return f"+{s['avg_up_swing_pct']:.2%} / -{s['avg_down_swing_pct']:.2%}".center(24)

    print(f"  {'-'*7}  " + "  ".join("-" * 24 for _ in days))
    print(f"  {'swing':>7}  " + "  ".join(
        swing_cell(result["by_day"][d]) for d in days))

    def base_cell(day_res):
        rec = day_res.get("recommended_ref")
        return f"{(rec or 'n/a'):^24}"

    print(f"  {'base':>7}  " + "  ".join(
        base_cell(result["by_day"][d]) for d in days))
    print()


def print_ticker_block(result: dict):
    ticker = result["ticker"]
    pcts = result["pcts"]
    pct_str = " / ".join(f"{p:.2%}" for p in pcts)
    print(bold("═" * 92))
    print(bold(f"  {ticker}  —  level thresholds ±{pct_str}"
               f"   (prior-day close baseline → scan-day touch)"))
    print(bold("═" * 92))
    print()

    for day_name in result["days"]:
        print_day_block(result, day_name)

    print_day_comparison(result)


def print_overall(all_results: dict):
    print(bold("\n" + "█" * 92))
    print(bold("  RECOMMENDED BASELINE — by ticker and day (steadiest reference)"))
    print(bold("█" * 92))
    for ticker, res in all_results.items():
        if ticker == "_meta":
            continue
        parts = []
        for day_name in res["days"]:
            d = res["by_day"][day_name]
            rec = d.get("recommended_ref")
            if rec is None:
                parts.append(f"{day_name} {yellow('n/a')}")
            else:
                parts.append(f"{day_name} {green(rec)} ({d['n_days']})")
        print(f"  {ticker:>6} : " + "   ".join(parts))
    print()


# ── CSV / TXT artifacts ───────────────────────────────────────────────────────
def _iter_tickers(all_results):
    return [(t, r) for t, r in all_results.items() if t != "_meta"]


def save_touch_summary_csv(path, all_results, lookback_days, source_label):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# Mon/Wed/Fri price-level-touch (percentage) — touch summary"])
        w.writerow([f"# Lookback = {lookback_days} calendar days  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        w.writerow([])
        w.writerow(["ticker", "day", "pct", "base_ref", "sessions",
                    "up_hits", "up_rate", "down_hits", "down_rate",
                    "both_hits", "both_rate", "neither_hits", "neither_rate",
                    "avg_up_swing_pct", "avg_down_swing_pct",
                    "max_up_swing_pct", "max_down_swing_pct",
                    "avg_up_swing", "avg_down_swing", "max_up_swing",
                    "max_down_swing", "recommended_baseline"])
        for ticker, res in _iter_tickers(all_results):
            for day_name in res["days"]:
                day_res = res["by_day"][day_name]
                rec = day_res.get("recommended_ref")
                for pct in res["pcts"]:
                    summaries = day_res["ref_summaries"][pct]
                    for lab in res["ref_labels"]:
                        s = summaries[lab]
                        if s["n"] == 0:
                            continue
                        w.writerow([
                            ticker, day_name, f"{pct:.4f}", lab, s["n"],
                            s["up_hits"], f"{s['up_rate']:.4f}",
                            s["down_hits"], f"{s['down_rate']:.4f}",
                            s["both"], f"{s['both_rate']:.4f}",
                            s["neither"], f"{s['neither_rate']:.4f}",
                            f"{s['avg_up_swing_pct']:.6f}", f"{s['avg_down_swing_pct']:.6f}",
                            f"{s['max_up_swing_pct']:.6f}", f"{s['max_down_swing_pct']:.6f}",
                            round(s["avg_up_swing"], 4), round(s["avg_down_swing"], 4),
                            round(s["max_up_swing_at_pct"], 4),
                            round(s["max_down_swing_at_pct"], 4),
                            "YES" if lab == rec else ""])


def save_swings_csv(path, all_results, lookback_days, source_label):
    """Long/tidy per-session ledger: one row per (day × session × reference × pct)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# Mon/Wed/Fri price-level-touch (percentage) — swing ledger"])
        w.writerow([f"# Lookback = {lookback_days} calendar days  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        w.writerow([])
        w.writerow(["date", "ticker", "day", "base_ref_time", "base_ref_price",
                    "pct", "threshold", "up_level", "down_level",
                    "sess_high", "sess_low",
                    "max_up_swing_pct", "max_down_swing_pct",
                    "max_up_swing", "max_down_swing", "touched_up", "touched_down",
                    "touched_both", "touched_neither"])
        for ticker, res in _iter_tickers(all_results):
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


def save_ticker_txt(path, result, lookback_days, source_label):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_ticker_block(result)
    pct_str = " / ".join(f"{p:.2%}" for p in result["pcts"])
    days_str = " / ".join(result["days"])
    hdr = (f"MON/WED/FRI PRICE-LEVEL-TOUCH (PERCENTAGE) — {result['ticker']} "
           f"(thresholds ±{pct_str})\n"
           f"Scan days = {days_str}  |  Lookback = {lookback_days} calendar days\n"
           f"Scan session = 9:30 AM–4:00 PM ET, 1-minute bars\n"
           f"Baseline = prior trading day 3:50–3:55 PM ET (per-minute) + 3:50–55 avg\n"
           f"Touch = scan-day session high/low reaches baseline × (1 ± pct)\n"
           f"Swings shown as % of reference (dollar move in brackets)\n"
           f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
           + "=" * 92 + "\n\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(hdr)
        fh.write(buf.getvalue())


# ── driver ────────────────────────────────────────────────────────────────────
def run_level_touch(lookback_days=None, header_extra=""):
    """Capture prior-day baselines + scan-day sessions per ticker across Mon/Wed/Fri,
    compute touch / swing stats, print and save results. Returns {ticker: result}."""
    config = Config()
    if lookback_days is not None:
        config.backtest_days = lookback_days
    lookback_days = config.backtest_days

    print(bold("\n" + "═" * 92))
    print(bold("  MON/WED/FRI PRICE-LEVEL-TOUCH ANALYSIS (PERCENTAGE)"))
    print(bold(f"  Scan days      : {', '.join(config.scan_days)}"))
    print(bold(f"  Lookback window: {lookback_days} calendar days"))
    print(bold("  Scan session   : 9:30 AM–4:00 PM ET, 1-minute bars"))
    print(bold("  Baseline       : prior trading day 3:50–3:55 PM ET + 3:50–55 average"))
    if header_extra:
        print(f"  {header_extra}")
    print(bold("═" * 92))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    pcts_by_ticker = config.ticker_pcts
    print("  Tickers / thresholds: "
          + "   ".join(f"{t} ±[{', '.join(f'{p:.2%}' for p in v)}]"
                       for t, v in pcts_by_ticker.items()))
    print()

    analyzer = LevelTouchAnalyzer(fetcher, config)
    raw = analyzer.run(list(pcts_by_ticker.keys()))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    all_results = {}
    for ticker in pcts_by_ticker.keys():
        res = analyze_ticker(raw[ticker])
        all_results[ticker] = res

        print(bold("\n" + "█" * 92))
        print_ticker_block(res)

        txt_path = os.path.join(
            RESULTS_DIR,
            f"level_touch_{ticker.lower()}_{lookback_days}days_{stamp}.txt")
        save_ticker_txt(txt_path, res, lookback_days, source_label)
        print(bold("─" * 92))
        print(f"  {cyan('Saved TXT:')} {bold(txt_path)}")
        print(bold("─" * 92))

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
