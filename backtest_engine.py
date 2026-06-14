#!/usr/bin/env python3
"""
Shared backtest engine for the three scoring-method scripts:

  custom_backtest.py    → score = win_rate × avg_payoff   (max expected profit)
  backtest_winrate.py   → score = win_rate                (max reliability)
  backtest_filtered.py  → score = win_rate × avg_payoff, but only among pairs
                          whose win_rate clears MIN_WIN_RATE (reliable + profit)

Each entry script just sets the knobs at the top, defines its scoring/eligibility,
and calls run(). All of them produce the same per-day P&L table, the same summary,
three heatmaps per ticker (win-rate %, win count, P&L), and a timestamped CSV.
"""

import contextlib
import csv
import io
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
from models import SOURCE_REAL
from utils.date_utils import minute_to_str

# 1 option contract controls 100 shares — payoff per share × 100 = dollars/contract.
CONTRACT_MULTIPLIER = 100

ENTRY_STEP = 5
MIN_HOLD = 5
MIN_SAMPLES = 3            # statistical floor: a pair needs >= 3 dates to count
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


def compute_pair_stats(reps: dict, size_fn=None) -> dict:
    """Stats for EVERY (entry, exit) pair across all dates — feeds the heatmaps.

    Returns {(entry_m, exit_m): {wr, wins, n, avg, total}} where avg/total are
    per-share (multiply by CONTRACT_MULTIPLIER for dollars per contract).

    size_fn(entry_price) -> int contracts. When given, each date's payoff is
    scaled by the contracts bought (per-share move × contracts), so avg/total
    reflect position-sized dollars/100. Wins are unaffected (the scale factor
    is always positive). Default None = 1 contract (original behaviour).
    """
    payoffs = defaultdict(list)
    for d, prices in reps.items():
        for entry_m in range(900, 951, ENTRY_STEP):           # 3:00 → 3:50
            ep, em = price_at(prices, entry_m)
            if ep is None or ep <= 0:
                continue
            qty = size_fn(ep) if size_fn else 1
            for exit_m in range(entry_m + MIN_HOLD, 960, ENTRY_STEP):  # … → 3:59
                xp, _ = price_at(prices, exit_m, after=em)
                if xp is None:
                    continue
                payoffs[(entry_m, exit_m)].append((xp - ep) * qty)

    stats = {}
    for (en, ex), pl in payoffs.items():
        if len(pl) < MIN_SAMPLES:
            continue
        wins = sum(1 for p in pl if p > 0)
        stats[(en, ex)] = {
            "entry": en, "exit": ex, "wins": wins, "n": len(pl),
            "wr": wins / len(pl), "avg": sum(pl) / len(pl), "total": sum(pl),
        }
    return stats


def find_optimal_pair(stats: dict, score_key, eligible):
    """Pick the best (entry, exit) using the caller's scoring + eligibility.

    score_key(stat)  -> sortable key (higher = better)
    eligible(stat)   -> bool (whether the pair may be chosen at all)
    Returns (best_stat | None, ranked_eligible_list).
    """
    elig = [s for s in stats.values() if eligible(s)]
    if not elig:
        return None, []
    ranked = sorted(elig, key=score_key, reverse=True)
    return ranked[0], ranked


def per_day_pnl(ticker: str, reps: dict, meta: dict, entry_m: int, exit_m: int,
                size_fn=None) -> list:
    """One row per MWF date: the ATM put bought at entry_m, sold at exit_m.

    size_fn(entry_price) -> int contracts. When given, pnl_dollars is scaled by
    the contract count and each row carries `contracts` + `cost_dollars`.
    Default None = 1 contract (original behaviour).
    """
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
                "payoff_per_share": "", "contracts": "", "cost_dollars": "",
                "pnl_dollars": "",
                "profitable": "", "note": "no usable price at entry/exit",
            })
            continue

        qty = size_fn(ep) if size_fn else 1
        payoff = xp - ep
        rows.append({
            "date": str(d), "ticker": ticker,
            "contract_symbol": rec["contract"], "strike": rec["strike"],
            "source": "REAL" if rec["source"] == SOURCE_REAL else "SIM",
            "entry_time": minute_to_str(em), "entry_price": round(ep, 4),
            "exit_time": minute_to_str(xm), "exit_price": round(xp, 4),
            "payoff_per_share": round(payoff, 4),
            "contracts": qty,
            "cost_dollars": round(ep * CONTRACT_MULTIPLIER * qty, 2),
            "pnl_dollars": round(payoff * CONTRACT_MULTIPLIER * qty, 2),
            "profitable": payoff > 0, "note": "",
        })
    return rows


def summarize(rows: list) -> dict:
    """Aggregate stats over the per-day rows that have a real result."""
    traded = [r for r in rows if r["pnl_dollars"] != ""]
    if not traded:
        return {"n": 0, "wins": 0, "win_rate": 0.0, "total_pnl": 0.0,
                "avg_pnl": 0.0, "best": 0.0, "worst": 0.0, "total_cost": 0.0,
                "n_skipped": len(rows)}
    pnls = [r["pnl_dollars"] for r in traded]
    wins = sum(1 for p in pnls if p > 0)
    costs = [r["cost_dollars"] for r in traded
             if isinstance(r.get("cost_dollars"), (int, float))]
    return {
        "n": len(traded), "wins": wins, "win_rate": wins / len(traded),
        "total_pnl": sum(pnls), "avg_pnl": sum(pnls) / len(pnls),
        "best": max(pnls), "worst": min(pnls),
        "total_cost": sum(costs) if costs else 0.0,
        "n_skipped": len(rows) - len(traded),
    }


# ── Heatmaps ───────────────────────────────────────────────────────────────
def _print_grid(title, stats, value_fn, color_fn, cell_w, optimal_key):
    """Generic entry↓ × exit→ grid. Cells via value_fn(stat); colored by color_fn."""
    entries = list(range(900, 951, ENTRY_STEP))   # 3:00 … 3:50
    exits   = list(range(905, 960, ENTRY_STEP))   # 3:05 … 3:55

    print(f"  {title}")
    header = f"  {'Entry':>7} |"
    for ex in exits:
        ex_s = minute_to_str(ex).replace(' PM', '').replace(' AM', '')
        header += f" {ex_s:>{cell_w}}"
    print(header)
    print(f"  {'-'*7}-+" + '-' * (cell_w + 1) * len(exits))

    for en in entries:
        en_s = minute_to_str(en).replace(' PM', '').replace(' AM', '')
        row = f"  {en_s:>7} |"
        for ex in exits:
            if ex <= en:
                row += f" {'·':>{cell_w}}"
                continue
            stat = stats.get((en, ex))
            if stat is None:
                row += f" {'':>{cell_w}}"
                continue
            raw = value_fn(stat)[:cell_w]
            cell = f"{raw:>{cell_w}}"
            if (en, ex) == optimal_key:
                cell = _c(cell, "1;36")          # optimal pick: bold cyan
            else:
                col = color_fn(stat)
                cell = col(cell) if col else cell
            row += f" {cell}"
        print(row)
    print()


def print_heatmaps(ticker, stats, optimal_key):
    """Three heatmaps for one ticker: win-rate %, win count, and P&L (avg + total)."""
    if not stats:
        print(f"  No heatmap data for {ticker}.\n")
        return

    print(f"  {bold(ticker + ' — HEATMAPS')}   (entry ↓  exit →   "
          f"{cyan('cyan')} = chosen optimal pair)\n")

    # 1) Win rate %
    def wr_val(s): return f"{s['wr']:.0%}"
    def wr_col(s):
        return green if s['wr'] >= 0.60 else (yellow if s['wr'] >= 0.50 else None)
    _print_grid("1) WIN RATE %  (wins ÷ trades)", stats, wr_val, wr_col, 6, optimal_key)

    # 2) Win count (raw number of winning trades)
    def wc_val(s): return f"{s['wins']}"
    def wc_col(s): return green if s['wr'] >= 0.50 else None
    _print_grid("2) WIN COUNT  (number of winning trades)",
                stats, wc_val, wc_col, 6, optimal_key)

    # 3a) Avg P&L per trade ($/contract)
    def avg_val(s): return f"{s['avg'] * CONTRACT_MULTIPLIER:+.0f}"
    def pnl_col(s): return green if s['avg'] > 0 else red
    _print_grid("3a) AVG P&L PER TRADE  ($ per contract)",
                stats, avg_val, pnl_col, 6, optimal_key)

    # 3b) Total P&L ($/contract)
    def tot_val(s): return f"{s['total'] * CONTRACT_MULTIPLIER:+.0f}"
    def tot_col(s): return green if s['total'] > 0 else red
    _print_grid("3b) TOTAL P&L  ($ per contract, summed over all dates)",
                stats, tot_val, tot_col, 7, optimal_key)


def print_ticker_block(ticker, best, rows, summ, result, show_qty=False):
    print(bold("=" * 78))
    print(bold(f"  {ticker}"))
    print(bold("=" * 78))
    if best is None:
        print(red("  No optimal entry/exit pair found "
                  "(no pair met the criteria / insufficient data).\n"))
        return

    en, ex = best["entry"], best["exit"]
    src = result.primary_source if result else "?"
    src_tag = (green("REAL prices") if src == "REAL"
               else yellow("MIXED real+sim") if src == "MIXED"
               else yellow("SIMULATED (Black-Scholes)") if src == "SIMULATED"
               else red("NO DATA"))
    print(f"  Optimal schedule : Buy {green(minute_to_str(en))}  "
          f"Sell {green(minute_to_str(ex))}")
    print(f"  Data source      : {src_tag}")
    print()
    qh = f"{'Qty':>4} " if show_qty else ""
    qs = f"{'-'*4} " if show_qty else ""
    print(f"  {'Date':<12} {'Strike':>8} {'Src':>4} {qh}{'Entry':>8} {'Buy$':>7} "
          f"{'Exit':>8} {'Sell$':>7} {'P&L/sh':>8} {'P&L $':>9}  Result")
    print(f"  {'-'*12} {'-'*8} {'-'*4} {qs}{'-'*8} {'-'*7} {'-'*8} {'-'*7} "
          f"{'-'*8} {'-'*9}  {'-'*6}")
    for r in rows:
        if r["pnl_dollars"] == "":
            qcell = f"{'—':>4} " if show_qty else ""
            print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
                  f"{qcell}{'—':>8} {'—':>7} {'—':>8} {'—':>7} {'—':>8} {'—':>9}  "
                  + yellow("skip"))
            continue
        res = green("WIN ") if r["profitable"] else red("LOSS")
        pnl = r["pnl_dollars"]
        pnl_s = green(f"${pnl:+.2f}") if pnl > 0 else red(f"${pnl:+.2f}")
        qcell = f"{r.get('contracts', 1):>4} " if show_qty else ""
        print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
              f"{qcell}{r['entry_time']:>8} {r['entry_price']:>7.2f} "
              f"{r['exit_time']:>8} {r['exit_price']:>7.2f} "
              f"{r['payoff_per_share']:>+8.3f} {pnl_s:>9}  {res}")

    print()
    tot = summ["total_pnl"]
    tot_s = green(f"${tot:+,.2f}") if tot >= 0 else red(f"${tot:+,.2f}")
    print(f"  {bold('SUMMARY (optimal pair)')}  "
          f"trades: {summ['n']}   "
          f"wins: {summ['wins']}/{summ['n']}   "
          f"win rate: {summ['win_rate']:.1%}   "
          f"total P&L: {tot_s}   "
          f"avg/trade: ${summ['avg_pnl']:+.2f}")
    print(f"           best day: ${summ['best']:+.2f}   "
          f"worst day: ${summ['worst']:+.2f}   "
          f"skipped (no data): {summ['n_skipped']}")
    if show_qty:
        cost = summ.get("total_cost", 0.0)
        roi = (summ["total_pnl"] / cost) if cost else 0.0
        roi_s = (green if roi >= 0 else red)(f"{roi:+.1%}")
        print(f"           premium spent: ${cost:,.2f}   "
              f"return on spend: {roi_s}")
    print()


def save_csv(method_label, header_extra, all_rows, ticker_summaries, grand,
             source_label, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"# Backtest method: {method_label}"])
        if header_extra:
            w.writerow([f"# {header_extra}"])
        w.writerow([f"# Lookback = {LOOKBACK_DAYS} calendar days"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares"])
        w.writerow([])

        # ── Per-day detail ──
        w.writerow(["DETAIL — one row per MWF date (ATM put at the optimal time)"])
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
        w.writerow(["ticker", "optimal_entry", "optimal_exit", "trades", "wins",
                    "win_rate", "total_pnl_dollars", "avg_pnl_dollars",
                    "best_day", "worst_day", "skipped_no_data"])
        for ts in ticker_summaries:
            w.writerow([ts["ticker"], ts["entry"], ts["exit"], ts["n"], ts["wins"],
                        f"{ts['win_rate']:.4f}", round(ts["total_pnl"], 2),
                        round(ts["avg_pnl"], 2), round(ts["best"], 2),
                        round(ts["worst"], 2), ts["n_skipped"]])
        w.writerow([])
        w.writerow(["GRAND TOTAL", "", "", grand["n"], grand["wins"],
                    f"{grand['win_rate']:.4f}", round(grand["total_pnl"], 2),
                    round(grand["avg_pnl"], 2), "", "", grand["n_skipped"]])


# LOOKBACK_DAYS is injected by the entry script before run() is called.
LOOKBACK_DAYS = 0


def run(lookback_days, method_label, score_key, eligible,
        file_tag, header_extra=""):
    """Main driver shared by all three scoring-method scripts."""
    global LOOKBACK_DAYS
    LOOKBACK_DAYS = lookback_days

    config = Config()
    config.backtest_days = lookback_days

    print(bold("\n" + "═" * 78))
    print(bold(f"  BACKTEST  —  {method_label}"))
    print(bold(f"  Lookback window: {lookback_days} calendar days"))
    if header_extra:
        print(f"  {header_extra}")
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
        stats = compute_pair_stats(reps)
        best, _ranked = find_optimal_pair(stats, score_key, eligible)
        if best is None:
            print_ticker_block(ticker, None, [], {}, results_by_ticker.get(ticker))
            continue

        en, ex = best["entry"], best["exit"]
        rows = per_day_pnl(ticker, reps, meta, en, ex)
        summ = summarize(rows)

        print_ticker_block(ticker, best, rows, summ, results_by_ticker.get(ticker))
        print_heatmaps(ticker, stats, (en, ex))

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
            "n": len(grand_pnls), "wins": wins, "win_rate": wins / len(grand_pnls),
            "total_pnl": sum(grand_pnls), "avg_pnl": sum(grand_pnls) / len(grand_pnls),
            "n_skipped": grand_skipped,
        }
    else:
        grand = {"n": 0, "wins": 0, "win_rate": 0.0, "total_pnl": 0.0,
                 "avg_pnl": 0.0, "n_skipped": grand_skipped}

    print(bold("═" * 78))
    print(bold(f"  GRAND TOTAL  —  {method_label}"))
    print(bold("═" * 78))
    gt = grand["total_pnl"]
    gt_s = green(f"${gt:+,.2f}") if gt >= 0 else red(f"${gt:+,.2f}")
    print(f"  Total trades : {grand['n']}")
    print(f"  Wins         : {grand['wins']}/{grand['n']}")
    print(f"  Win rate     : {grand['win_rate']:.1%}")
    print(f"  Total P&L    : {gt_s}   (1 contract per ticker per MWF)")
    print(f"  Avg / trade  : ${grand['avg_pnl']:+.2f}")
    print()

    # ── Save timestamped file (method tag keeps simultaneous runs separate) ──
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    fname = f"backtest_{file_tag}_{lookback_days}days_{stamp}.csv"
    path = os.path.join(RESULTS_DIR, fname)
    save_csv(method_label, header_extra, all_rows, ticker_summaries, grand,
             source_label, path)

    print(bold("─" * 78))
    print(f"  {cyan('Saved:')} {bold(path)}")
    print(f"  Open it in Excel/Sheets — per-day detail on top, summary at the bottom.")
    print(bold("─" * 78))
    print()


# ── Day-of-week helpers ────────────────────────────────────────────────────

class _MockResult:
    """Lightweight stand-in for BacktestResult used only to carry a source tag."""
    def __init__(self, src: str):
        self.primary_source = src


def _source_from_rows(rows: list) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED"
    if "REAL" in srcs:
        return "REAL"
    if "SIM" in srcs:
        return "SIMULATED"
    return "NONE"


def _combo_stats(day_data, tickers, combo_days):
    """Aggregate P&L for a set of tickers over a bundle of weekdays."""
    pnls = [r["pnl_dollars"]
            for tk in tickers
            for dn in combo_days
            for r in (day_data.get((tk, dn)) or {}).get("rows", [])
            if r["pnl_dollars"] != ""]
    if not pnls:
        return None
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls)
    return {"n": n, "wins": wins, "win_rate": wins / n,
            "total": total, "avg": total / n}


def _save_byday_csv(method_label, header_extra, day_data, tickers, days, combos,
                    source_label, lookback_days, path, sized=False):
    """CSV output for the by-day backtest.

    sized — when True, the detail and summary sections gain position-sizing
    columns (contracts, cost, return-on-spend). Default False keeps the
    original schema unchanged.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# Backtest method: {method_label}  (by day of week)"])
        if header_extra:
            w.writerow([f"# {header_extra}"])
        w.writerow([f"# Lookback = {lookback_days} calendar days"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares"])
        w.writerow([])

        # Per-day detail rows
        size_cols = ["contracts", "cost_dollars"] if sized else []
        w.writerow(["DETAIL — one row per MWF date; each day uses its own optimal timing"])
        w.writerow(["day_of_week", "date", "ticker", "contract_symbol", "strike",
                    "source", "entry_time", "entry_price", "exit_time", "exit_price",
                    "payoff_per_share"] + size_cols +
                   ["pnl_dollars", "profitable", "note"])
        for day_name, _ in days:
            for ticker in tickers:
                dr = day_data.get((ticker, day_name))
                if dr is None:
                    continue
                for r in dr["rows"]:
                    size_vals = ([r.get("contracts", ""), r.get("cost_dollars", "")]
                                 if sized else [])
                    w.writerow([day_name, r["date"], r["ticker"], r["contract_symbol"],
                                r["strike"], r["source"], r["entry_time"], r["entry_price"],
                                r["exit_time"], r["exit_price"], r["payoff_per_share"]]
                               + size_vals +
                               [r["pnl_dollars"], r["profitable"], r["note"]])
        w.writerow([])

        # Per-ticker × per-day summary
        sum_cols = ["premium_spent", "return_on_spend"] if sized else []
        w.writerow(["SUMMARY BY DAY"])
        w.writerow(["day_of_week", "ticker", "optimal_entry", "optimal_exit",
                    "trades", "wins", "win_rate", "total_pnl_dollars", "avg_pnl_dollars",
                    "best_day", "worst_day", "skipped_no_data"] + sum_cols)
        for day_name, _ in days:
            for ticker in tickers:
                dr = day_data.get((ticker, day_name))
                if dr is None:
                    w.writerow([day_name, ticker, "—", "—", 0, 0,
                                "0.0000", 0.0, 0.0, 0.0, 0.0, 0]
                               + (["", ""] if sized else []))
                    continue
                s = dr["summ"]
                if sized:
                    cost = s.get("total_cost", 0.0)
                    roi = (s["total_pnl"] / cost) if cost else 0.0
                    extra = [round(cost, 2), f"{roi:.4f}"]
                else:
                    extra = []
                w.writerow([day_name, ticker,
                            minute_to_str(dr["best"]["entry"]),
                            minute_to_str(dr["best"]["exit"]),
                            s["n"], s["wins"], f"{s['win_rate']:.4f}",
                            round(s["total_pnl"], 2), round(s["avg_pnl"], 2),
                            round(s["best"], 2), round(s["worst"], 2),
                            s["n_skipped"]] + extra)
        w.writerow([])

        # Combo comparison — per equity, then all combined
        w.writerow(["DAY COMBINATION COMPARISON (per equity, then ALL combined)"])
        w.writerow(["ticker", "combination", "days_included", "trades", "wins",
                    "win_rate", "total_pnl_dollars", "avg_pnl_dollars"])
        scopes = [(tk, [tk]) for tk in tickers] + [("ALL", tickers)]
        for scope_name, scope_list in scopes:
            for combo_name, combo_days in combos:
                cs = _combo_stats(day_data, scope_list, combo_days)
                if cs is None:
                    w.writerow([scope_name, combo_name, "+".join(combo_days),
                                0, 0, "0.0000", 0.0, 0.0])
                    continue
                w.writerow([scope_name, combo_name, "+".join(combo_days),
                            cs["n"], cs["wins"], f"{cs['win_rate']:.4f}",
                            round(cs["total"], 2), round(cs["avg"], 2)])


def run_byday(lookback_days, method_label, score_key, eligible,
              file_tag, header_extra="", days=None, combos=None, size_fn=None):
    """Day-of-week driver: finds a separate optimal (entry, exit) per weekday.

    days    — list of (day_name, weekday_int); defaults to Mon/Wed/Fri.
    combos  — list of (label, [day_name, ...]) bundles for the comparison table;
              defaults to all 7 Mon/Wed/Fri combinations.
    size_fn — optional size_fn(entry_price) -> int contracts. When given, P&L
              and the optimizer reflect position sizing, and contract/cost
              columns appear in the output. Default None = 1 contract.
    The combo table is printed per equity and then for all tickers combined.
    """
    global LOOKBACK_DAYS
    LOOKBACK_DAYS = lookback_days

    config = Config()
    config.backtest_days = lookback_days

    DAYS = days if days is not None else [
        ("Monday", 0), ("Wednesday", 2), ("Friday", 4)]
    if combos is not None:
        COMBOS = combos
    else:
        COMBOS = [
            ("Monday only",    ["Monday"]),
            ("Wednesday only", ["Wednesday"]),
            ("Friday only",    ["Friday"]),
            ("Mon + Wed",      ["Monday", "Wednesday"]),
            ("Mon + Fri",      ["Monday", "Friday"]),
            ("Wed + Fri",      ["Wednesday", "Friday"]),
            ("All 3 days",     ["Monday", "Wednesday", "Friday"]),
        ]

    day_names = [d[0] for d in DAYS]
    scope = "BY DAY" if len(DAYS) > 1 else f"{day_names[0].upper()} ONLY"

    print(bold("\n" + "═" * 78))
    print(bold(f"  BACKTEST {scope}  —  {method_label}"))
    print(bold(f"  Lookback window: {lookback_days} calendar days"))
    if header_extra:
        print(f"  {header_extra}")
    print(bold("═" * 78))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    print(f"  Tickers: {', '.join(config.tickers)}")
    print(f"  Finding optimal timing separately for {', '.join(day_names)}.\n")

    backtester = Backtester(fetcher, config)
    backtester.capture_daily = True
    backtester.run(config.tickers)

    # ── Compute per-ticker × per-weekday stats ─────────────────────────────
    day_data = {}   # {(ticker, day_name): {best, rows, summ, stats, optimal_key} | None}

    for ticker in config.tickers:
        records = backtester.daily_capture.get(ticker, [])
        for day_name, wday in DAYS:
            day_recs = [r for r in records if r["date"].weekday() == wday]
            if len(day_recs) < MIN_SAMPLES:
                day_data[(ticker, day_name)] = None
                continue
            reps, meta = build_representatives(day_recs)
            stats = compute_pair_stats(reps, size_fn)
            best, _ = find_optimal_pair(stats, score_key, eligible)
            if best is None:
                day_data[(ticker, day_name)] = None
                continue
            en, ex = best["entry"], best["exit"]
            rows = per_day_pnl(ticker, reps, meta, en, ex, size_fn)
            summ = summarize(rows)
            day_data[(ticker, day_name)] = {
                "best": best, "rows": rows, "summ": summ,
                "stats": stats, "optimal_key": (en, ex),
            }

    # ── Print routines (called twice: terminal + plain-text capture) ───────
    def _print_combo_table(tickers, label):
        multi = len(COMBOS) > 1
        print(bold("\n" + "═" * 78))
        print(bold(f"  {label}"))
        if multi:
            print(bold("  P&L if you traded only the selected day(s),"))
            print(bold("  each at that day's own optimal time  (1 contract each)"))
        print(bold("═" * 78))
        print(f"  {'Combination':<22}  {'Trades':>6}  {'Wins':>5}  {'Win%':>6}  "
              f"{'Total P&L':>12}  {'Avg/trade':>10}")
        print(f"  {'-'*22}  {'-'*6}  {'-'*5}  {'-'*6}  {'-'*12}  {'-'*10}")
        for combo_name, combo_days in COMBOS:
            cs = _combo_stats(day_data, tickers, combo_days)
            if cs is None:
                print(f"  {combo_name:<22}  (no data)")
                continue
            tot_s = (green if cs["total"] >= 0 else red)(f"${cs['total']:+,.2f}")
            print(f"  {combo_name:<22}  {cs['n']:>6}  {cs['wins']:>5}  "
                  f"{cs['win_rate']:>5.1%}  {tot_s:>12}  ${cs['avg']:>+9.2f}")
        print()

    def _print_all():
        for ticker in config.tickers:
            print(bold("\n" + "═" * 78))
            print(bold(f"  {ticker}"))
            print(bold("═" * 78))
            for day_name, _ in DAYS:
                dr = day_data.get((ticker, day_name))
                print(f"\n  {'─' * 4} {day_name} {'─' * 4}")
                if dr is None:
                    print(red("  No optimal pair found "
                              "(insufficient data or no pair met the criteria)."))
                    continue
                mock = _MockResult(_source_from_rows(dr["rows"]))
                print_ticker_block(ticker, dr["best"], dr["rows"], dr["summ"], mock,
                                   show_qty=(size_fn is not None))
                print_heatmaps(ticker, dr["stats"], dr["optimal_key"])
            # This equity's own combo table, right after its day blocks
            _print_combo_table([ticker], f"{ticker} — DAY COMBINATION COMPARISON")
        # Whole-portfolio view (all tickers combined) at the very bottom
        _print_combo_table(config.tickers,
                           "ALL TICKERS COMBINED — DAY COMBINATION COMPARISON")

    # Print to terminal (ANSI colours if TTY)
    _print_all()

    # Capture plain-text version for the .txt file
    # (redirect_stdout to StringIO → sys.stdout.isatty() returns False →
    #  _c() emits no ANSI codes, so the captured string is clean plain text)
    txt_buf = io.StringIO()
    with contextlib.redirect_stdout(txt_buf):
        _print_all()
    txt_content = txt_buf.getvalue()

    # ── Save files ─────────────────────────────────────────────────────────
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base = f"backtest_{file_tag}_{lookback_days}days_{stamp}"
    csv_path = os.path.join(RESULTS_DIR, f"{base}.csv")
    txt_path = os.path.join(RESULTS_DIR, f"{base}.txt")

    _save_byday_csv(method_label, header_extra, day_data, config.tickers,
                    DAYS, COMBOS, source_label, lookback_days, csv_path,
                    sized=(size_fn is not None))

    hdr = (f"BACKTEST BY DAY — {method_label}\n"
           f"Lookback = {lookback_days} calendar days\n"
           f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
           f"P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares\n"
           + "=" * 78 + "\n\n")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(hdr)
        f.write(txt_content)

    print(bold("─" * 78))
    print(f"  {cyan('Saved CSV:')} {bold(csv_path)}")
    print(f"  {cyan('Saved TXT:')} {bold(txt_path)}")
    print(f"  CSV: structured data (detail + summary + combos).")
    print(f"  TXT: full heatmap output in plain text — open in any text editor.")
    print(bold("─" * 78))
    print()
