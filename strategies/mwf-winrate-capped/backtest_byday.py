#!/usr/bin/env python3
"""
MON/WED/FRI 0DTE — WIN-RATE-CAPPED optimal entry/exit study  (TSLA & AAPL)

Finds the best (entry, exit) time for a 0DTE option on Monday, Wednesday and
Friday, for BOTH calls and puts, on TSLA and AAPL — but *instead of an outlier
system*, it constrains the SELECTED schedule by WIN RATE. Only (entry, exit)
pairs whose win rate lands inside a target band are eligible, so the chosen
"best day" is a realistic 45-50% (±1%) rather than an overfit, sky-high win rate.

    eligible ⇔ (MAX_WIN_RATE_LOW - WIN_RATE_TOL) <= win_rate <= (MAX_WIN_RATE_HIGH + WIN_RATE_TOL)

Position sizing matches the sized backtests: contracts = ceil(TARGET_SPEND /
option_price), min 1 (TARGET_SPEND is the per-share premium floor; $1.00 ≈ $100).

Each weekday uses its own lookback and trading window (below). Run standalone for
a terminal summary:  python backtest_byday.py   ·   the pipeline entry point is
strategy.py, which wraps run_all() and emits the metrics/trades/chart contract.

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE LINES:                                                 ║
║    DAY_SCHEDULE      — per-weekday lookback (days) + trading window   ║
║    TARGET_SPEND      — minimum premium per share ($1.00 = ~$100)     ║
║    MAX_WIN_RATE_LOW  — lower edge of the target win-rate band         ║
║    MAX_WIN_RATE_HIGH — upper edge (the "up to 50%" cap)               ║
║    WIN_RATE_TOL      — ± tolerance around the band                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os
# Cap BLAS thread pools to 1 before NumPy loads (via analysis.backtester's pandas
# import inside run_all) — avoids the OpenBLAS "Memory allocation still failed
# after 10 retries" abort on the runner. Harmless when strategy.py already set it.
for _blas_var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                  "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_blas_var, "1")

import math
from datetime import date, timedelta

from config import Config
from byday_engine import (
    build_representatives, compute_pair_stats, find_optimal_pair,
    per_day_pnl, summarize, CONTRACT_MULTIPLIER, MIN_SAMPLES,
)

# ── Per-weekday schedule ────────────────────────────────────────────────────
# (day_name, weekday_int, lookback_days, window_start_hour, window_end_hour)
# Monday/Wednesday: 140 days, 3-4 PM ET.   Friday: 730 days, 2-4 PM ET.
DAY_SCHEDULE = [
    ("Monday",    0, 140, 15, 16),
    ("Wednesday", 2, 140, 15, 16),
    ("Friday",    4, 730, 14, 16),
]

TARGET_SPEND = 1.00          # <───── minimum premium per share per trade

# ── WIN-RATE CAP (replaces the old OUTLIER_MAX system) ──────────────────────
# The selected "best day" must have a win rate inside the band below, so it
# lands at a realistic 45-50% instead of an overfit high win rate.
MAX_WIN_RATE_LOW  = 0.45     # <───── lower edge of the target win-rate band
MAX_WIN_RATE_HIGH = 0.50     # <───── upper edge of the band (the "up to 50%" cap)
WIN_RATE_TOL      = 0.01     # <───── ± tolerance → eligible band [0.44, 0.51]


def size_fn(entry_price):
    """Buy enough contracts to spend at least TARGET_SPEND/share (min 1)."""
    if entry_price <= 0:
        return 1
    return max(1, math.ceil(TARGET_SPEND / entry_price))


def score_key(s):
    """Rank by win_rate × avg_payoff (tiny win_rate tiebreaker when avg <= 0)."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def eligible(s):
    """Only pairs whose win rate lands in the target band are eligible, so the
    chosen 'best day' is a realistic 45-50% (±1%) rather than overfit."""
    lo = MAX_WIN_RATE_LOW - WIN_RATE_TOL
    hi = MAX_WIN_RATE_HIGH + WIN_RATE_TOL
    return lo <= s["wr"] <= hi


def band_str() -> str:
    lo, hi = MAX_WIN_RATE_LOW - WIN_RATE_TOL, MAX_WIN_RATE_HIGH + WIN_RATE_TOL
    return f"[{lo:.0%}, {hi:.0%}]"


def get_fetcher():
    """Alpaca if keys present, else yfinance fallback."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher
    if ALPACA_AVAILABLE:
        f = AlpacaFetcher.from_env()
        if f is not None:
            return f, "Alpaca Markets API"
    return YFinanceFetcher(), "yfinance (set ALPACA_API_KEY for real option data)"


def run_all():
    """Capture MWF data once (both tickers, both option types) and score each
    (ticker, weekday, option type) with the win-rate cap applied.

    Returns (all_results, meta) where all_results is keyed by
    (ticker, day_name, opt_type) -> {best, ranked, rows, summ, window, lookback}
    | None, and meta carries the run-level provenance/config.
    """
    from analysis.backtester import Backtester

    config = Config()
    config.backtest_days = max(d[2] for d in DAY_SCHEDULE)  # capture the longest
    # Capture window = union of every weekday's window.
    config.window_start_minute = min(d[3] for d in DAY_SCHEDULE) * 60
    config.window_end_minute = max(d[4] for d in DAY_SCHEDULE) * 60

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    print(f"  Tickers: {', '.join(config.tickers)}   "
          f"Option types: {', '.join(config.option_types)}")
    print(f"  Win-rate cap: best day must land in {band_str()} "
          f"(target {MAX_WIN_RATE_LOW:.0%}-{MAX_WIN_RATE_HIGH:.0%}).\n")

    backtester = Backtester(fetcher, config)
    backtester.run(config.tickers)

    today = date.today()
    all_results = {}
    for ticker in config.tickers:
        for opt_type in config.option_types:
            records = backtester.daily_capture.get((ticker, opt_type), [])
            for day_name, wday, lookback, win_sh, win_eh in DAY_SCHEDULE:
                cutoff = today - timedelta(days=lookback)
                day_recs = [r for r in records
                            if r["date"].weekday() == wday and r["date"] >= cutoff]
                key = (ticker, day_name, opt_type)
                # Count only rows that actually carry price data toward the floor.
                usable = [r for r in day_recs if r.get("prices")]
                if len(usable) < MIN_SAMPLES:
                    all_results[key] = None
                    continue
                ws_m, we_m = win_sh * 60, win_eh * 60
                reps, meta = build_representatives(day_recs)
                stats = compute_pair_stats(reps, ws_m, we_m, size_fn)
                best, ranked = find_optimal_pair(stats, score_key, eligible)
                if best is None:
                    all_results[key] = None
                    continue
                en, ex = best["entry"], best["exit"]
                rows = per_day_pnl(ticker, opt_type, reps, meta, en, ex, size_fn)
                summ = summarize(rows)
                all_results[key] = {
                    "best": best, "ranked": ranked, "rows": rows, "summ": summ,
                    "window": (win_sh, win_eh), "lookback": lookback,
                }

    run_meta = {
        "tickers": list(config.tickers),
        "option_types": list(config.option_types),
        "data_source": source_label,
        "schedule": DAY_SCHEDULE,
        "target_spend": TARGET_SPEND,
        "win_rate_band": [MAX_WIN_RATE_LOW - WIN_RATE_TOL,
                          MAX_WIN_RATE_HIGH + WIN_RATE_TOL],
        "win_rate_target": [MAX_WIN_RATE_LOW, MAX_WIN_RATE_HIGH],
    }
    return all_results, run_meta


def _opt_word(ot):
    return "CALL" if ot == "C" else "PUT"


def _print_report(all_results):
    from byday_engine import price_at  # noqa: F401 (kept for parity/debug)
    print("\n" + "=" * 74)
    print(f"  MON/WED/FRI WIN-RATE-CAPPED 0DTE  —  best schedule per "
          f"ticker/day/type   band {band_str()}")
    print("=" * 74)
    hdr = f"  {'Ticker':<6} {'Day':<10} {'Type':<5} {'Entry':>7} {'Exit':>7} " \
          f"{'Win%':>6} {'Trades':>7} {'Total$':>11} {'Avg$':>9}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for (ticker, day, ot), res in sorted(all_results.items()):
        if not res:
            print(f"  {ticker:<6} {day:<10} {_opt_word(ot):<5}   (no eligible schedule)")
            continue
        b, s = res["best"], res["summ"]
        from utils.date_utils import minute_to_str
        print(f"  {ticker:<6} {day:<10} {_opt_word(ot):<5} "
              f"{minute_to_str(b['entry']):>7} {minute_to_str(b['exit']):>7} "
              f"{s['win_rate']*100:>5.0f}% {s['n']:>7} "
              f"${s['total_pnl']:>10,.0f} ${s['avg_pnl']:>+8,.0f}")
    print("=" * 74 + "\n")


if __name__ == "__main__":
    results, _meta = run_all()
    _print_report(results)
