#!/usr/bin/env python3
"""
MWF CONCENTRATION-CAPPED BACKTEST — target-spend sized, both calls & puts.

Finds, for each (ticker, weekday, option type), the best fixed 5-minute
(entry_time, exit_time) schedule inside that day's trading window, ranking
schedules by win_rate × avg_payoff (max expected profit) — but only among
schedules that pass the single-transaction CONCENTRATION CAP:

    single_trade_share = (largest single winning trade P&L) / (net total P&L)
    eligible  ⇔  net_total_pnl > 0  AND  single_trade_share <= MAX_SINGLE_TRADE_SHARE

so no timeframe is crowned "best" just because one lucky trade carried it. This
REPLACES the old outlier system entirely (no OUTLIER_MAX, no winning-trade
dollar-drop pass).

Scope (see config.py): TSLA & AAPL, Monday / Wednesday / Friday, both option
types. Monday & Wednesday = 140-day lookback, 3-4 PM ET; Friday = 730-day
lookback, 2-4 PM ET with a Thursday fallback for closed sessions.

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE LINES:                                                 ║
║    MAX_SINGLE_TRADE_SHARE — max share of net total P&L one winning   ║
║                            trade may hold for the schedule to qualify║
║    TARGET_SPEND           — minimum premium per share ($1.00 ≈ $100) ║
╚══════════════════════════════════════════════════════════════════════╝
"""

MAX_SINGLE_TRADE_SHARE = 0.51   # <── biggest single win may be ≤ ~50% (±1%) of total
TARGET_SPEND           = 1.00   # <── minimum premium per share per trade

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_concentration.py
# ──────────────────────────────────────────────────────────────────────────
import math

from config import Config
from concentration_engine import (
    CONTRACT_MULTIPLIER, MIN_SAMPLES,
    build_representatives, compute_pair_stats, find_optimal_pair,
    per_day_pnl, summarize, opt_word,
)
from models import SOURCE_NO_STOCK
from utils.date_utils import minute_to_str


def size_fn(entry_price):
    """Buy enough contracts to spend at least TARGET_SPEND/share (min 1)."""
    if entry_price <= 0:
        return 1
    return max(1, math.ceil(TARGET_SPEND / entry_price))


def score_key(s):
    """Rank by win_rate × avg_payoff (tiny win_rate tiebreaker when avg <= 0)."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def make_eligible(max_single_trade_share):
    """Concentration-cap eligibility closure.

    A schedule qualifies only when its net total P&L is positive AND its largest
    single winning trade is at most `max_single_trade_share` of that total. A
    schedule with no winning trade, or a non-positive total (share undefined),
    is ineligible.
    """
    def eligible(s):
        total = s["total"]
        max_win = s["max_win"]
        if total <= 0 or max_win is None:
            return False
        return (max_win / total) <= max_single_trade_share
    return eligible


# ── ANSI helpers (no-op when piped) ────────────────────────────────────────
import sys


def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def green(t):  return _c(t, "32")
def red(t):    return _c(t, "31")
def yellow(t): return _c(t, "33")
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "36")


def get_fetcher():
    """Alpaca if keys present, else yfinance fallback."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher
    if ALPACA_AVAILABLE:
        f = AlpacaFetcher.from_env()
        if f is not None:
            return f, "Alpaca Markets API"
    return YFinanceFetcher(), "yfinance (set ALPACA_API_KEY for real option data)"


def _source_from_rows(rows: list) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED"
    if "REAL" in srcs:
        return "REAL"
    if "SIM" in srcs:
        return "SIMULATED"
    return "NONE"


def _print_combo_block(ticker, day_name, opt_type, res):
    print(bold("─" * 82))
    head = f"  {ticker} {day_name} {opt_word(opt_type)}S"
    print(bold(head))
    print(bold("─" * 82))
    if res is None or res.get("best") is None:
        print(red("  No eligible schedule (concentration cap not met, or "
                  "insufficient data).\n"))
        return
    best = res["best"]
    summ = res["summ"]
    share = best["single_trade_share"] or 0.0
    src = _source_from_rows(res["rows"])
    src_tag = (green("REAL") if src == "REAL" else yellow(src))
    print(f"  Optimal schedule    : Buy {green(minute_to_str(best['entry']))}  "
          f"Sell {green(minute_to_str(best['exit']))}   ({src_tag} prices)")
    tot = summ["total_pnl"]
    tot_s = green(f"${tot:+,.2f}") if tot >= 0 else red(f"${tot:+,.2f}")
    print(f"  Win rate / total P&L: {summ['win_rate']:.1%}  "
          f"({summ['wins']}/{summ['n']})   {tot_s}")
    share_s = (green if share <= 0.51 else yellow)(f"{share:.1%}")
    biggest = (best["max_win"] or 0.0) * CONTRACT_MULTIPLIER
    print(f"  Single-trade share  : {share_s}   "
          f"(biggest single win ${biggest:,.2f} of total P&L — cap held)")
    print()


def run_concentration(max_single_trade_share=MAX_SINGLE_TRADE_SHARE,
                      target_spend=TARGET_SPEND):
    """Driver: capture MWF data (calls + puts) and pick the best concentration-
    capped schedule per (ticker, weekday, option type). Returns
    {(ticker, day_name, opt_type): result_dict | None}.
    """
    # size_fn closes over target_spend for parity with the module-level default.
    def _size_fn(entry_price):
        if entry_price <= 0:
            return 1
        return max(1, math.ceil(target_spend / entry_price))

    eligible = make_eligible(max_single_trade_share)

    config = Config()

    print(bold("\n" + "═" * 82))
    print(bold("  MWF CONCENTRATION-CAPPED BACKTEST — win_rate × avg_payoff, "
               "target-spend sized"))
    print(bold(f"  Concentration cap: single winning trade ≤ "
               f"{max_single_trade_share:.0%} of net total P&L"))
    print(bold(f"  Position sizing  : contracts = ceil(${target_spend:.2f} / "
               f"entry_price), min 1"))
    print(bold("═" * 82))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    print(f"  Tickers: {', '.join(config.tickers)}   "
          f"Option types: {', '.join(opt_word(o) for o in config.option_types)}")
    for spec in config.days:
        print(f"    {spec.name:<9} lookback {spec.lookback_days:>3}d   "
              f"window {minute_to_str(spec.window_start_minute)}–"
              f"{minute_to_str(spec.window_end_minute)}"
              + ("  (Thu fallback)" if spec.thursday_fallback else ""))
    print()

    from analysis.backtester import Backtester
    backtester = Backtester(fetcher, config)
    backtester.run(config.tickers)

    all_results = {}
    for ticker in config.tickers:
        for spec in config.days:
            for opt_type in config.option_types:
                records = backtester.daily_capture.get((ticker, opt_type, spec.name), [])
                usable = [r for r in records if r["source"] != SOURCE_NO_STOCK]
                if len(usable) < MIN_SAMPLES:
                    all_results[(ticker, spec.name, opt_type)] = None
                    _print_combo_block(ticker, spec.name, opt_type, None)
                    continue

                reps, meta = build_representatives(records)
                stats = compute_pair_stats(
                    reps, spec.window_start_minute, spec.window_end_minute, _size_fn)
                best, ranked = find_optimal_pair(stats, score_key, eligible)
                if best is None:
                    all_results[(ticker, spec.name, opt_type)] = None
                    _print_combo_block(ticker, spec.name, opt_type, None)
                    continue

                rows = per_day_pnl(ticker, reps, meta, best["entry"], best["exit"],
                                   _size_fn)
                summ = summarize(rows)
                res = {"best": best, "rows": rows, "summ": summ, "ranked": ranked,
                       "day": spec.name,
                       "window": (spec.window_start_minute, spec.window_end_minute),
                       "lookback_days": spec.lookback_days}
                all_results[(ticker, spec.name, opt_type)] = res
                _print_combo_block(ticker, spec.name, opt_type, res)

    return all_results, source_label


if __name__ == "__main__":
    run_concentration()
