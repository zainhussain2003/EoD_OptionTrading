#!/usr/bin/env python3
"""
CUSTOM-RANGE BACKTEST  —  day-by-day P&L over any look-back window you choose.

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THIS ONE LINE to test any window (e.g. 100, 250, 500 days):   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 100          # <───── EDIT ONLY THIS LINE (calendar days to test)

# ──────────────────────────────────────────────────────────────────────────
# Everything below is the engine. You normally don't need to touch it.
# Run with:   python custom_backtest.py
# ──────────────────────────────────────────────────────────────────────────

import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

# Load .env if present (Alpaca credentials)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import Config
from analysis.backtester import Backtester
from models import SOURCE_REAL, SOURCE_SIM
from utils.date_utils import minute_to_str

# 1 option contract controls 100 shares — payoff per share × 100 = dollars/contract.
CONTRACT_MULTIPLIER = 100

ENTRY_STEP = 5
MIN_HOLD = 5
RESULTS_DIR = "backtest_results"


# ── tiny ANSI helpers (no-op when output is piped to a file) ──────────────
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


def price_at(prices: dict, target_m: int, after: int | None = None):
    """Price at target minute, falling back to the nearest bar within one step.

    Returns (price, actual_minute) or (None, None) if nothing usable is near.
    """
    if target_m in prices and (after is None or target_m > after):
        return prices[target_m], target_m
    cands = [m for m in prices
             if abs(m - target_m) <= ENTRY_STEP and (after is None or m > after)]
    if not cands:
        return None, None
    m = min(cands, key=lambda x: abs(x - target_m))
    return prices[m], m


def build_representatives(records: list) -> tuple[dict, dict]:
    """One contract per date: prefer REAL bars, then the strike closest to spot.

    Returns ({date: {minute: price}}, {date: meta_record}).
    """
    by_date = defaultdict(list)
    for r in records:
        by_date[r["date"]].append(r)

    reps, meta = {}, {}
    for d, recs in by_date.items():
        real = [r for r in recs if r["source"] == SOURCE_REAL]
        pool = real or recs
        rep = min(pool, key=lambda r: abs(r["strike"] - r["spot_3pm"]))
        reps[d] = rep["prices"]
        meta[d] = rep
    return reps, meta


def find_optimal_pair(reps: dict):
    """Brute-force every (entry, exit) over the representative daily series.

    Returns (best_pair_tuple, ranked_pairs). Each pair tuple is
    (entry_m, exit_m, win_rate, avg_payoff, score, n_samples).
    """
    payoffs = defaultdict(list)
    for d, prices in reps.items():
        for entry_m in range(900, 951, ENTRY_STEP):       # 3:00 → 3:50
            ep, em = price_at(prices, entry_m)
            if ep is None or ep <= 0:
                continue
            for exit_m in range(entry_m + MIN_HOLD, 960, ENTRY_STEP):  # … → 3:59
                xp, _ = price_at(prices, exit_m, after=em)
                if xp is None:
                    continue
                payoffs[(entry_m, exit_m)].append(xp - ep)

    pairs = []
    for (en, ex), pl in payoffs.items():
        if len(pl) < 3:                                   # statistical floor
            continue
        wins = sum(1 for p in pl if p > 0)
        wr = wins / len(pl)
        avg = sum(pl) / len(pl)
        score = wr * max(avg, 0.0) + wr * 0.001
        pairs.append((en, ex, wr, avg, score, len(pl)))

    pairs.sort(key=lambda x: x[4], reverse=True)
    best = pairs[0] if pairs else None
    return best, pairs


def per_day_pnl(ticker: str, reps: dict, meta: dict, entry_m: int, exit_m: int) -> list:
    """One row per MWF date: the ATM call bought at entry_m, sold at exit_m."""
    rows = []
    for d in sorted(reps.keys()):
        prices = reps[d]
        rec = meta[d]
        ep, em = price_at(prices, entry_m)
        xp, xm = price_at(prices, exit_m, after=em)

        if ep is None or xp is None or ep <= 0:
            rows.append({
                "date": str(d), "ticker": ticker,
                "contract_symbol": rec["contract"], "strike": rec["strike"],
                "source": "REAL" if rec["source"] == SOURCE_REAL else "SIM",
                "entry_time": minute_to_str(entry_m), "entry_price": "",
                "exit_time": minute_to_str(exit_m), "exit_price": "",
                "payoff_per_share": "", "pnl_dollars": "",
                "profitable": "", "note": "no usable price at entry/exit",
            })
            continue

        payoff = xp - ep
        rows.append({
            "date": str(d), "ticker": ticker,
            "contract_symbol": rec["contract"], "strike": rec["strike"],
            "source": "REAL" if rec["source"] == SOURCE_REAL else "SIM",
            "entry_time": minute_to_str(em), "entry_price": round(ep, 4),
            "exit_time": minute_to_str(xm), "exit_price": round(xp, 4),
            "payoff_per_share": round(payoff, 4),
            "pnl_dollars": round(payoff * CONTRACT_MULTIPLIER, 2),
            "profitable": payoff > 0, "note": "",
        })
    return rows


def summarize(rows: list) -> dict:
    """Aggregate stats over the per-day rows that have a real result."""
    traded = [r for r in rows if r["pnl_dollars"] != ""]
    if not traded:
        return {"n": 0, "wins": 0, "win_rate": 0.0, "total_pnl": 0.0,
                "avg_pnl": 0.0, "best": 0.0, "worst": 0.0, "n_skipped": len(rows)}
    pnls = [r["pnl_dollars"] for r in traded]
    wins = sum(1 for p in pnls if p > 0)
    return {
        "n": len(traded), "wins": wins, "win_rate": wins / len(traded),
        "total_pnl": sum(pnls), "avg_pnl": sum(pnls) / len(pnls),
        "best": max(pnls), "worst": min(pnls),
        "n_skipped": len(rows) - len(traded),
    }


def print_ticker_block(ticker, best, rows, summ, result):
    print(bold("=" * 78))
    print(bold(f"  {ticker}"))
    print(bold("=" * 78))
    if best is None:
        print(red("  No optimal entry/exit pair found (insufficient data in window).\n"))
        return

    en, ex, wr, avg, _score, n = best
    src = result.primary_source if result else "?"
    src_tag = (green("REAL prices") if src == "REAL"
               else yellow("MIXED real+sim") if src == "MIXED"
               else yellow("SIMULATED (Black-Scholes)") if src == "SIMULATED"
               else red("NO DATA"))
    print(f"  Optimal schedule : Buy {green(minute_to_str(en))}  "
          f"Sell {green(minute_to_str(ex))}")
    print(f"  Data source      : {src_tag}")
    print()
    print(f"  {'Date':<12} {'Strike':>8} {'Src':>4} {'Entry':>8} {'Buy$':>7} "
          f"{'Exit':>8} {'Sell$':>7} {'P&L/sh':>8} {'P&L $':>9}  Result")
    print(f"  {'-'*12} {'-'*8} {'-'*4} {'-'*8} {'-'*7} {'-'*8} {'-'*7} "
          f"{'-'*8} {'-'*9}  {'-'*6}")
    for r in rows:
        if r["pnl_dollars"] == "":
            print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
                  f"{'—':>8} {'—':>7} {'—':>8} {'—':>7} {'—':>8} {'—':>9}  "
                  + yellow("skip"))
            continue
        res = green("WIN ") if r["profitable"] else red("LOSS")
        pnl = r["pnl_dollars"]
        pnl_s = green(f"${pnl:+.2f}") if pnl > 0 else red(f"${pnl:+.2f}")
        print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
              f"{r['entry_time']:>8} {r['entry_price']:>7.2f} "
              f"{r['exit_time']:>8} {r['exit_price']:>7.2f} "
              f"{r['payoff_per_share']:>+8.3f} {pnl_s:>9}  {res}")

    print()
    tot = summ["total_pnl"]
    tot_s = green(f"${tot:+,.2f}") if tot >= 0 else red(f"${tot:+,.2f}")
    print(f"  {bold('SUMMARY')}  "
          f"trades: {summ['n']}   "
          f"win rate: {summ['win_rate']:.1%}   "
          f"total P&L: {tot_s}   "
          f"avg/trade: ${summ['avg_pnl']:+.2f}")
    print(f"           best day: ${summ['best']:+.2f}   "
          f"worst day: ${summ['worst']:+.2f}   "
          f"skipped (no data): {summ['n_skipped']}")
    print()


def save_csv(all_rows, ticker_summaries, grand, source_label, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"# Custom backtest  |  lookback = {LOOKBACK_DAYS} calendar days"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares"])
        w.writerow([])

        # ── Per-day detail ──
        w.writerow(["DETAIL — one row per MWF date (ATM call at the optimal time)"])
        w.writerow(["date", "ticker", "contract_symbol", "strike", "source",
                    "entry_time", "entry_price", "exit_time", "exit_price",
                    "payoff_per_share", "pnl_dollars", "profitable", "note"])
        for r in all_rows:
            w.writerow([r["date"], r["ticker"], r["contract_symbol"], r["strike"],
                        r["source"], r["entry_time"], r["entry_price"],
                        r["exit_time"], r["exit_price"], r["payoff_per_share"],
                        r["pnl_dollars"], r["profitable"], r["note"]])

        # ── Per-ticker + grand summary ──
        w.writerow([])
        w.writerow(["SUMMARY — overall performance"])
        w.writerow(["ticker", "optimal_entry", "optimal_exit", "trades",
                    "win_rate", "total_pnl_dollars", "avg_pnl_dollars",
                    "best_day", "worst_day", "skipped_no_data"])
        for ts in ticker_summaries:
            w.writerow([ts["ticker"], ts["entry"], ts["exit"], ts["n"],
                        f"{ts['win_rate']:.4f}", round(ts["total_pnl"], 2),
                        round(ts["avg_pnl"], 2), round(ts["best"], 2),
                        round(ts["worst"], 2), ts["n_skipped"]])
        w.writerow([])
        w.writerow(["GRAND TOTAL", "", "", grand["n"],
                    f"{grand['win_rate']:.4f}", round(grand["total_pnl"], 2),
                    round(grand["avg_pnl"], 2), "", "", grand["n_skipped"]])


def main():
    config = Config()
    config.backtest_days = LOOKBACK_DAYS

    print(bold("\n" + "═" * 78))
    print(bold(f"  CUSTOM BACKTEST  —  lookback window: {LOOKBACK_DAYS} calendar days"))
    print(bold("═" * 78))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    print(f"  Tickers: {', '.join(config.tickers)}")
    print(f"  Testing all 5-min entry/exit pairs in the 3:00–3:55 PM ET window.\n")

    backtester = Backtester(fetcher, config)
    backtester.capture_daily = True
    results = backtester.run(config.tickers)
    results_by_ticker = {r.ticker: r for r in results}

    all_rows = []
    ticker_summaries = []
    grand_pnls = []
    grand_skipped = 0

    for ticker in config.tickers:
        records = backtester.daily_capture.get(ticker, [])
        if not records:
            print(bold("=" * 78))
            print(bold(f"  {ticker}"))
            print(red("  No data captured for this ticker.\n"))
            continue

        reps, meta = build_representatives(records)
        best, _pairs = find_optimal_pair(reps)
        if best is None:
            print_ticker_block(ticker, None, [], {}, results_by_ticker.get(ticker))
            continue

        en, ex = best[0], best[1]
        rows = per_day_pnl(ticker, reps, meta, en, ex)
        summ = summarize(rows)

        print_ticker_block(ticker, best, rows, summ, results_by_ticker.get(ticker))

        all_rows.extend(rows)
        ticker_summaries.append({
            "ticker": ticker, "entry": minute_to_str(en), "exit": minute_to_str(ex),
            **summ,
        })
        grand_pnls.extend([r["pnl_dollars"] for r in rows if r["pnl_dollars"] != ""])
        grand_skipped += summ["n_skipped"]

    # ── Grand total ──
    if grand_pnls:
        wins = sum(1 for p in grand_pnls if p > 0)
        grand = {
            "n": len(grand_pnls), "win_rate": wins / len(grand_pnls),
            "total_pnl": sum(grand_pnls), "avg_pnl": sum(grand_pnls) / len(grand_pnls),
            "n_skipped": grand_skipped,
        }
    else:
        grand = {"n": 0, "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                 "n_skipped": grand_skipped}

    print(bold("═" * 78))
    print(bold("  GRAND TOTAL (all tickers, every MWF in window)"))
    print(bold("═" * 78))
    gt = grand["total_pnl"]
    gt_s = green(f"${gt:+,.2f}") if gt >= 0 else red(f"${gt:+,.2f}")
    print(f"  Total trades : {grand['n']}")
    print(f"  Win rate     : {grand['win_rate']:.1%}")
    print(f"  Total P&L    : {gt_s}   (1 contract per ticker per MWF)")
    print(f"  Avg / trade  : ${grand['avg_pnl']:+.2f}")
    print()

    # ── Save timestamped file ──
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    fname = f"backtest_{LOOKBACK_DAYS}days_{stamp}.csv"
    path = os.path.join(RESULTS_DIR, fname)
    save_csv(all_rows, ticker_summaries, grand, source_label, path)

    print(bold("─" * 78))
    print(f"  {cyan('Saved:')} {bold(path)}")
    print(f"  Open it in Excel/Sheets — per-day detail on top, summary at the bottom.")
    print(bold("─" * 78))
    print()


if __name__ == "__main__":
    main()
