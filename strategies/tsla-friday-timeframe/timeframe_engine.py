#!/usr/bin/env python3
"""
Time-frame search engine for the TSLA Friday optimal entry/exit study.

Unlike the narrow-window backtests (which test fixed 5-minute entry/exit points
inside a one-hour window), this engine works over the WHOLE regular session
(9:30 AM–4:00 PM ET) and searches for the best entry/exit *time frames* — each a
contiguous window [start, end] of arbitrary length (5 minutes up to the full day,
and not snapped to clean 5-minute marks: 12:32–12:45 is fair game).

A frame's price is the MEAN of the 1-minute closes inside it (noise reduction).
A trade enters during the entry frame at mean(entry) and exits during the exit
frame at mean(exit), with exit_start >= entry_end so every exit minute is strictly
after every entry minute. P&L/share = mean(exit) − mean(entry), position-sized by
size_fn (target-spend), scored by win_rate × avg_payoff — same as friday_sized.

Search is two-stage (coarse → fine):
  1. COARSE: frame boundaries on a 5-minute grid over a duration list spanning
     5 minutes to the full day. Per-Friday prefix sums make each frame mean O(1).
  2. FINE:   the winning frames' four boundaries are slid ±5 min at 1-minute
     resolution and re-scored, so the result can land on odd boundaries.

Output mirrors friday_sized: per-Friday P&L table, SUMMARY line (with premium
spent + return on spend), four heatmaps (win-rate %, win count, avg P&L, total
P&L) on a coarse entry-start × exit-start grid, a ranked Top-15 frame-pairs table,
and a $-threshold "outliers removed" second pass. Calls and puts are both run and
each writes its own CSV + TXT (+ *_outliers_removed.txt) into backtest_results/.
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
from models import SOURCE_REAL, SOURCE_NO_STOCK
from utils.date_utils import minute_to_str

# 1 option contract controls 100 shares — payoff per share × 100 = dollars/contract.
CONTRACT_MULTIPLIER = 100

MIN_SAMPLES = 3            # a frame pair needs >= 3 Fridays to count
MIN_DUR = 5               # shortest frame considered (minutes)
COARSE_STEP = 5           # coarse boundary grid (minutes)
REFINE_RADIUS = 5         # fine pass slides each boundary ±this many minutes (1-min)
HEATMAP_BUCKET = 30       # heatmap axes group frame starts into 30-min buckets
TOP_N = 15                # size of the ranked frame-pairs table
RESULTS_DIR = "backtest_results"

# Candidate frame durations for the coarse pass — 5 minutes up to the full day
# (no cap). A duration list (rather than every possible length) is what keeps the
# uncapped search fast; the fine pass then refines the boundaries to the minute.
DURATIONS = [5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180, 240, 300, 390]

# Regular session window in minutes-of-day (9:30 AM = 570 → 4:00 PM = 960).
# run_timeframe() overrides these from config so every part of the engine tracks
# the chosen window.
DAY_START_M = 570
DAY_END_M = 960

# LOOKBACK_DAYS is injected by the entry script before run_timeframe() is called.
LOOKBACK_DAYS = 0


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


def _hm(m: int) -> tuple[str, str]:
    """(clock, period) for a minute-of-day, e.g. 752 -> ('12:32', 'PM')."""
    h, mm = m // 60, m % 60
    period = 'AM' if h < 12 else 'PM'
    dh = h % 12
    if dh == 0:
        dh = 12
    return f"{dh}:{mm:02d}", period


def frame_label(start: int, end: int) -> str:
    """Compact frame label, e.g. (752, 767) -> '12:32–12:47 PM'."""
    s, sp = _hm(start)
    e, ep = _hm(end)
    return f"{s}–{e} {ep}" if sp == ep else f"{s} {sp}–{e} {ep}"


def opt_word(opt_type: str) -> str:
    return "CALL" if opt_type == 'C' else "PUT"


def opt_tag(opt_type: str) -> str:
    return "calls" if opt_type == 'C' else "puts"


# ── data shaping ────────────────────────────────────────────────────────────
def build_representatives(records: list) -> tuple[dict, dict]:
    """One contract per Friday: prefer REAL bars, then the strike closest to spot.

    Returns ({date: {minute: price}}, {date: meta_record}).
    """
    by_date = defaultdict(list)
    for r in records:
        by_date[r["date"]].append(r)

    reps, meta = {}, {}
    for d, recs in by_date.items():
        real = [r for r in recs if r["source"] == SOURCE_REAL]
        pool = real or recs
        rep = min(pool, key=lambda r: abs(r["strike"] - r["spot_open"]))
        reps[d] = rep["prices"]
        meta[d] = rep
    return reps, meta


def build_index(prices: dict) -> tuple[list, list]:
    """Prefix sums over the session so any frame's mean is O(1).

    Returns (psum, pcnt) of length N+1 where N = DAY_END_M - DAY_START_M and
    index i corresponds to minute DAY_START_M + i.
    """
    n = DAY_END_M - DAY_START_M
    psum = [0.0] * (n + 1)
    pcnt = [0] * (n + 1)
    for i in range(n):
        p = prices.get(DAY_START_M + i)
        psum[i + 1] = psum[i] + (p if p is not None else 0.0)
        pcnt[i + 1] = pcnt[i] + (1 if p is not None else 0)
    return psum, pcnt


def frame_mean(index, start: int, end: int):
    """Mean of the available 1-min closes in [start, end), or None if none."""
    psum, pcnt = index
    si, ei = start - DAY_START_M, end - DAY_START_M
    cnt = pcnt[ei] - pcnt[si]
    if cnt == 0:
        return None
    return (psum[ei] - psum[si]) / cnt


# ── scoring ─────────────────────────────────────────────────────────────────
def pair_stat(payoffs: list, outlier_max=None):
    """Win-rate / avg / total over a frame pair's per-Friday payoffs (per share,
    already scaled by contracts). outlier_max drops WINNING trades whose dollar
    P&L exceeds the threshold before computing the stats."""
    pl = payoffs
    if outlier_max is not None:
        pl = [p for p in pl if p * CONTRACT_MULTIPLIER <= outlier_max]
    if len(pl) < MIN_SAMPLES:
        return None
    n = len(pl)
    wins = sum(1 for p in pl if p > 0)
    return {"wins": wins, "n": n, "wr": wins / n,
            "avg": sum(pl) / n, "total": sum(pl)}


def enumerate_coarse_frames() -> list:
    """All (start, end) frames on the coarse grid for the duration list."""
    frames = []
    for start in range(DAY_START_M, DAY_END_M, COARSE_STEP):
        for dur in DURATIONS:
            end = start + dur
            if end <= DAY_END_M:
                frames.append((start, end))
    return frames


def coarse_search(index_by_date, size_fn, score_key, eligible, outlier_max=None):
    """Stage 1: score every coarse (entry frame, exit frame) pair.

    Returns (best_stat | None, ranked_stats, cell_best) where cell_best maps a
    (entry_start_bucket, exit_start_bucket) heatmap cell to its best-scoring stat.
    """
    frames = enumerate_coarse_frames()

    # Per-frame {date: mean} (only Fridays with a usable, positive mean).
    fmeans = {}
    for f in frames:
        s, e = f
        d2m = {}
        for d, idx in index_by_date.items():
            m = frame_mean(idx, s, e)
            if m is not None and m > 0:
                d2m[d] = m
        fmeans[f] = d2m

    best, best_score = None, -float("inf")
    ranked, cell_best = [], {}

    for ef in frames:
        es, ee = ef
        efm = fmeans[ef]
        if len(efm) < MIN_SAMPLES:
            continue
        for xf in frames:
            xs, xe = xf
            if xs < ee:                       # exit frame must start at/after entry end
                continue
            xfm = fmeans[xf]
            if len(xfm) < MIN_SAMPLES:
                continue

            small, big = (efm, xfm) if len(efm) <= len(xfm) else (xfm, efm)
            payoffs = []
            for d in small:
                if d in big:
                    em = efm[d]
                    payoffs.append((xfm[d] - em) * size_fn(em))

            stat = pair_stat(payoffs, outlier_max)
            if stat is None:
                continue
            stat.update({"es": es, "ee": ee, "xs": xs, "xe": xe})
            if not eligible(stat):
                continue

            sc = score_key(stat)
            ranked.append(stat)
            eb = (es - DAY_START_M) // HEATMAP_BUCKET
            xb = (xs - DAY_START_M) // HEATMAP_BUCKET
            cur = cell_best.get((eb, xb))
            if cur is None or sc > score_key(cur):
                cell_best[(eb, xb)] = stat
            if sc > best_score:
                best_score, best = sc, stat

    ranked.sort(key=score_key, reverse=True)
    return best, ranked, cell_best


def refine_search(index_by_date, best, size_fn, score_key, eligible, outlier_max=None):
    """Stage 2: slide the winner's four boundaries ±REFINE_RADIUS at 1-min
    resolution and re-score, landing on minute-precise frames."""
    if best is None:
        return None
    es0, ee0, xs0, xe0 = best["es"], best["ee"], best["xs"], best["xe"]

    def rng(c):
        return range(max(DAY_START_M, c - REFINE_RADIUS),
                     min(DAY_END_M, c + REFINE_RADIUS) + 1)

    best_ref, best_sc = best, score_key(best)
    for es in rng(es0):
        for ee in rng(ee0):
            if ee - es < MIN_DUR:
                continue
            for xs in rng(xs0):
                if xs < ee:
                    continue
                for xe in rng(xe0):
                    if xe - xs < MIN_DUR or xe > DAY_END_M:
                        continue
                    payoffs = []
                    for idx in index_by_date.values():
                        em = frame_mean(idx, es, ee)
                        if em is None or em <= 0:
                            continue
                        xm = frame_mean(idx, xs, xe)
                        if xm is None:
                            continue
                        payoffs.append((xm - em) * size_fn(em))
                    stat = pair_stat(payoffs, outlier_max)
                    if stat is None:
                        continue
                    stat.update({"es": es, "ee": ee, "xs": xs, "xe": xe})
                    if not eligible(stat):
                        continue
                    sc = score_key(stat)
                    if sc > best_sc:
                        best_sc, best_ref = sc, stat
    return best_ref


# ── per-Friday detail for the chosen frame pair ─────────────────────────────
def per_day_pnl(opt_type, reps, meta, index_by_date, frame, size_fn) -> list:
    """One row per Friday for the chosen (entry frame, exit frame)."""
    es, ee, xs, xe = frame["es"], frame["ee"], frame["xs"], frame["xe"]
    en_lbl, ex_lbl = frame_label(es, ee), frame_label(xs, xe)
    rows = []
    for d in sorted(reps.keys()):
        rec = meta[d]
        idx = index_by_date[d]
        em = frame_mean(idx, es, ee)
        xm = frame_mean(idx, xs, xe)

        if em is None or xm is None or em <= 0:
            if rec.get("source") == SOURCE_NO_STOCK:
                skip_src = "MISS"
                skip_note = rec.get("note") or "missing data (market closed)"
            else:
                skip_src = "REAL" if rec["source"] == SOURCE_REAL else "SIM"
                skip_note = "no usable price in entry/exit frame"
            rows.append({
                "date": str(d), "opt_type": opt_type,
                "contract_symbol": rec["contract"], "strike": rec["strike"],
                "source": skip_src,
                "entry_frame": en_lbl, "entry_price": "",
                "exit_frame": ex_lbl, "exit_price": "",
                "payoff_per_share": "", "contracts": "", "cost_dollars": "",
                "pnl_dollars": "", "profitable": "", "note": skip_note,
            })
            continue

        qty = size_fn(em)
        payoff = xm - em
        rows.append({
            "date": str(d), "opt_type": opt_type,
            "contract_symbol": rec["contract"], "strike": rec["strike"],
            "source": "REAL" if rec["source"] == SOURCE_REAL else "SIM",
            "entry_frame": en_lbl, "entry_price": round(em, 4),
            "exit_frame": ex_lbl, "exit_price": round(xm, 4),
            "payoff_per_share": round(payoff, 4),
            "contracts": qty,
            "cost_dollars": round(em * CONTRACT_MULTIPLIER * qty, 2),
            "pnl_dollars": round(payoff * CONTRACT_MULTIPLIER * qty, 2),
            "profitable": payoff > 0, "note": rec.get("note", ""),
        })
    return rows


def summarize(rows: list) -> dict:
    """Aggregate stats over the per-Friday rows that have a real result."""
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


def _remove_outlier_rows(rows, outlier_max):
    """Drop winning rows whose dollar P&L exceeds outlier_max."""
    kept, removed = [], []
    for r in rows:
        if r["pnl_dollars"] != "" and r["pnl_dollars"] > outlier_max:
            removed.append(r["date"])
        else:
            kept.append(r)
    return kept, removed


def _source_from_rows(rows: list) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED"
    if "REAL" in srcs:
        return "REAL"
    if "SIM" in srcs:
        return "SIMULATED"
    return "NONE"


# ── printing ────────────────────────────────────────────────────────────────
def print_block(ticker, opt_type, frame, rows, summ):
    print(bold("=" * 86))
    print(bold(f"  {ticker} {opt_word(opt_type)}S"))
    print(bold("=" * 86))
    if frame is None:
        print(red("  No optimal entry/exit frame found "
                  "(insufficient data / no pair met the criteria).\n"))
        return

    src = _source_from_rows(rows)
    src_tag = (green("REAL prices") if src == "REAL"
               else yellow("MIXED real+sim") if src == "MIXED"
               else yellow("SIMULATED (Black-Scholes)") if src == "SIMULATED"
               else red("NO DATA"))
    en_dur = frame["ee"] - frame["es"]
    ex_dur = frame["xe"] - frame["xs"]
    print(f"  Optimal entry frame : {green(frame_label(frame['es'], frame['ee']))}"
          f"   ({en_dur} min)")
    print(f"  Optimal exit frame  : {green(frame_label(frame['xs'], frame['xe']))}"
          f"   ({ex_dur} min)")
    print(f"  Data source         : {src_tag}")
    print()

    print(f"  {'Date':<12} {'Strike':>8} {'Src':>4} {'Qty':>4} "
          f"{'Entry frame':>17} {'Buy$':>7} {'Exit frame':>17} {'Sell$':>7} "
          f"{'P&L/sh':>8} {'P&L $':>10}  Result")
    print(f"  {'-'*12} {'-'*8} {'-'*4} {'-'*4} {'-'*17} {'-'*7} {'-'*17} {'-'*7} "
          f"{'-'*8} {'-'*10}  {'-'*6}")
    for r in rows:
        if r["pnl_dollars"] == "":
            print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
                  f"{'—':>4} {r['entry_frame']:>17} {'—':>7} "
                  f"{r['exit_frame']:>17} {'—':>7} {'—':>8} {'—':>10}  "
                  + yellow("skip"))
            continue
        res = green("WIN ") if r["profitable"] else red("LOSS")
        pnl = r["pnl_dollars"]
        pnl_s = green(f"${pnl:+.2f}") if pnl > 0 else red(f"${pnl:+.2f}")
        print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
              f"{r['contracts']:>4} {r['entry_frame']:>17} {r['entry_price']:>7.2f} "
              f"{r['exit_frame']:>17} {r['exit_price']:>7.2f} "
              f"{r['payoff_per_share']:>+8.3f} {pnl_s:>10}  {res}")

    print()
    tot = summ["total_pnl"]
    tot_s = green(f"${tot:+,.2f}") if tot >= 0 else red(f"${tot:+,.2f}")
    print(f"  {bold('SUMMARY (optimal frames)')}  "
          f"trades: {summ['n']}   wins: {summ['wins']}/{summ['n']}   "
          f"win rate: {summ['win_rate']:.1%}   total P&L: {tot_s}   "
          f"avg/trade: ${summ['avg_pnl']:+.2f}")
    print(f"           best day: ${summ['best']:+.2f}   "
          f"worst day: ${summ['worst']:+.2f}   "
          f"skipped (no data): {summ['n_skipped']}")
    cost = summ.get("total_cost", 0.0)
    roi = (summ["total_pnl"] / cost) if cost else 0.0
    roi_s = (green if roi >= 0 else red)(f"{roi:+.1%}")
    print(f"           premium spent: ${cost:,.2f}   return on spend: {roi_s}")
    print()


def _bucket_labels() -> list:
    n = (DAY_END_M - DAY_START_M) // HEATMAP_BUCKET
    out = []
    for b in range(n):
        s, _ = _hm(DAY_START_M + b * HEATMAP_BUCKET)
        out.append(s)
    return out


def _print_grid(title, cell_best, value_fn, color_fn, cell_w, optimal_cell):
    """Generic entry-start-bucket ↓ × exit-start-bucket → grid."""
    labels = _bucket_labels()
    n = len(labels)

    print(f"  {title}")
    header = f"  {'Entry':>7} |"
    for lab in labels:
        header += f" {lab:>{cell_w}}"
    print(header)
    print(f"  {'-'*7}-+" + '-' * (cell_w + 1) * n)

    for eb in range(n):
        row = f"  {labels[eb]:>7} |"
        for xb in range(n):
            if xb < eb:
                row += f" {'·':>{cell_w}}"
                continue
            stat = cell_best.get((eb, xb))
            if stat is None:
                row += f" {'':>{cell_w}}"
                continue
            raw = value_fn(stat)[:cell_w]
            cell = f"{raw:>{cell_w}}"
            if (eb, xb) == optimal_cell:
                cell = _c(cell, "1;36")
            else:
                col = color_fn(stat)
                cell = col(cell) if col else cell
            row += f" {cell}"
        print(row)
    print()


def print_heatmaps(ticker, opt_type, cell_best, optimal_cell):
    """Four heatmaps over the coarse entry-start × exit-start grid; each cell is
    the best-scoring frame pair whose entry/exit START falls in that 30-min bucket."""
    if not cell_best:
        print(f"  No heatmap data for {ticker} {opt_word(opt_type)}s.\n")
        return

    print(f"  {bold(ticker + ' ' + opt_word(opt_type) + 'S — HEATMAPS')}   "
          f"(entry-frame start ↓  exit-frame start →   "
          f"{cyan('cyan')} = chosen optimal)\n")
    print("  Each cell = best frame pair starting in that 30-min bucket "
          "(best over all durations).\n")

    def wr_val(s): return f"{s['wr']:.0%}"
    def wr_col(s):
        return green if s['wr'] >= 0.60 else (yellow if s['wr'] >= 0.50 else None)
    _print_grid("1) WIN RATE %  (wins ÷ trades)", cell_best, wr_val, wr_col, 6,
                optimal_cell)

    def wc_val(s): return f"{s['wins']}"
    def wc_col(s): return green if s['wr'] >= 0.50 else None
    _print_grid("2) WIN COUNT  (number of winning trades)", cell_best, wc_val,
                wc_col, 6, optimal_cell)

    def avg_val(s): return f"{s['avg'] * CONTRACT_MULTIPLIER:+.0f}"
    def pnl_col(s): return green if s['avg'] > 0 else red
    _print_grid("3a) AVG P&L PER TRADE  ($ per contract)", cell_best, avg_val,
                pnl_col, 6, optimal_cell)

    def tot_val(s): return f"{s['total'] * CONTRACT_MULTIPLIER:+.0f}"
    def tot_col(s): return green if s['total'] > 0 else red
    _print_grid("3b) TOTAL P&L  ($ per contract, summed over all Fridays)",
                cell_best, tot_val, tot_col, 7, optimal_cell)


def print_top_pairs(ticker, opt_type, ranked, chosen):
    print(bold("─" * 86))
    print(bold(f"  {ticker} {opt_word(opt_type)}S — TOP {TOP_N} FRAME PAIRS "
               f"(by win_rate × avg payoff)"))
    print(bold("─" * 86))
    print(f"  {'#':>2}  {'Entry frame':>17}  {'Exit frame':>17}  {'Trades':>6}  "
          f"{'Wins':>5}  {'Win%':>6}  {'Avg P&L':>9}  {'Total P&L':>12}")
    print(f"  {'-'*2}  {'-'*17}  {'-'*17}  {'-'*6}  {'-'*5}  {'-'*6}  "
          f"{'-'*9}  {'-'*12}")
    if not ranked:
        print("  (no eligible frame pairs)\n")
        return
    chosen_key = ((chosen["es"], chosen["ee"], chosen["xs"], chosen["xe"])
                  if chosen else None)
    for i, s in enumerate(ranked[:TOP_N], 1):
        en = frame_label(s["es"], s["ee"])
        ex = frame_label(s["xs"], s["xe"])
        avg_s = f"${s['avg'] * CONTRACT_MULTIPLIER:+.2f}"
        tot_s = f"${s['total'] * CONTRACT_MULTIPLIER:+,.2f}"
        line = (f"  {i:>2}  {en:>17}  {ex:>17}  {s['n']:>6}  {s['wins']:>5}  "
                f"{s['wr']:>5.1%}  {avg_s:>9}  {tot_s:>12}")
        # Note: the chosen optimal is the refined frame; if it appears here mark it.
        if chosen_key and (s["es"], s["ee"], s["xs"], s["xe"]) == chosen_key:
            line = cyan(line)
        print(line)
    print()


# ── CSV ─────────────────────────────────────────────────────────────────────
def save_csv(opt_type, method_label, header_extra, rows, summ, frame, ranked,
             source_label, lookback_days, win_tag, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# Backtest method: {method_label}  ({opt_word(opt_type)}s)"])
        if header_extra:
            w.writerow([f"# {header_extra}"])
        w.writerow([f"# Lookback = {lookback_days} calendar days"])
        w.writerow([f"# Session window = {win_tag} ET (full regular session)"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares"])
        if frame is not None:
            w.writerow([f"# Optimal entry frame = {frame_label(frame['es'], frame['ee'])}"
                        f"  |  Optimal exit frame = {frame_label(frame['xs'], frame['xe'])}"])
        w.writerow([])

        # Per-Friday detail
        w.writerow(["DETAIL — one row per Friday (ATM "
                    f"{opt_word(opt_type).lower()} at the optimal frames)"])
        w.writerow(["date", "opt_type", "contract_symbol", "strike", "source",
                    "entry_frame", "entry_price", "exit_frame", "exit_price",
                    "payoff_per_share", "contracts", "cost_dollars",
                    "pnl_dollars", "profitable", "note"])
        for r in rows:
            w.writerow([r["date"], r["opt_type"], r["contract_symbol"], r["strike"],
                        r["source"], r["entry_frame"], r["entry_price"],
                        r["exit_frame"], r["exit_price"], r["payoff_per_share"],
                        r["contracts"], r["cost_dollars"], r["pnl_dollars"],
                        r["profitable"], r["note"]])
        w.writerow([])

        # Summary
        w.writerow(["SUMMARY — optimal frames"])
        w.writerow(["opt_type", "optimal_entry_frame", "optimal_exit_frame",
                    "trades", "wins", "win_rate", "total_pnl_dollars",
                    "avg_pnl_dollars", "best_day", "worst_day", "skipped_no_data",
                    "premium_spent", "return_on_spend"])
        cost = summ.get("total_cost", 0.0)
        roi = (summ["total_pnl"] / cost) if cost else 0.0
        w.writerow([
            opt_word(opt_type),
            frame_label(frame["es"], frame["ee"]) if frame else "—",
            frame_label(frame["xs"], frame["xe"]) if frame else "—",
            summ["n"], summ["wins"], f"{summ['win_rate']:.4f}",
            round(summ["total_pnl"], 2), round(summ["avg_pnl"], 2),
            round(summ["best"], 2), round(summ["worst"], 2), summ["n_skipped"],
            round(cost, 2), f"{roi:.4f}"])
        w.writerow([])

        # Top frame pairs
        w.writerow([f"TOP {TOP_N} FRAME PAIRS (by win_rate × avg payoff)"])
        w.writerow(["rank", "entry_frame", "exit_frame", "trades", "wins",
                    "win_rate", "avg_pnl_dollars", "total_pnl_dollars"])
        for i, s in enumerate(ranked[:TOP_N], 1):
            w.writerow([i, frame_label(s["es"], s["ee"]),
                        frame_label(s["xs"], s["xe"]), s["n"], s["wins"],
                        f"{s['wr']:.4f}", round(s["avg"] * CONTRACT_MULTIPLIER, 2),
                        round(s["total"] * CONTRACT_MULTIPLIER, 2)])


# ── orchestration ───────────────────────────────────────────────────────────
def _analyze(opt_type, records, size_fn, score_key, eligible, outlier_max):
    """Run the full coarse→fine search for one option type. Returns a dict of
    everything the printers and CSV need (normal pass + outliers-removed pass)."""
    reps, meta = build_representatives(records)
    index_by_date = {d: build_index(prices) for d, prices in reps.items()}

    # Normal pass
    best, ranked, cell_best = coarse_search(
        index_by_date, size_fn, score_key, eligible)
    frame = refine_search(index_by_date, best, size_fn, score_key, eligible)
    rows = per_day_pnl(opt_type, reps, meta, index_by_date, frame, size_fn) if frame else []
    summ = summarize(rows)

    out = {"reps": reps, "meta": meta, "index": index_by_date,
           "frame": frame, "rows": rows, "summ": summ,
           "ranked": ranked, "cell_best": cell_best}

    # Outliers-removed pass: re-score with winning outliers dropped, re-optimize.
    if outlier_max is not None:
        b2, r2, c2 = coarse_search(
            index_by_date, size_fn, score_key, eligible, outlier_max=outlier_max)
        f2 = refine_search(index_by_date, b2, size_fn, score_key, eligible,
                           outlier_max=outlier_max)
        rows2 = (per_day_pnl(opt_type, reps, meta, index_by_date, f2, size_fn)
                 if f2 else [])
        rows2, removed = _remove_outlier_rows(rows2, outlier_max)
        out["excl"] = {"frame": f2, "rows": rows2, "summ": summarize(rows2),
                       "ranked": r2, "cell_best": c2, "removed": removed}
    return out


def _optimal_cell(frame):
    if frame is None:
        return None
    return ((frame["es"] - DAY_START_M) // HEATMAP_BUCKET,
            (frame["xs"] - DAY_START_M) // HEATMAP_BUCKET)


def run_timeframe(lookback_days, method_label, score_key, eligible, size_fn,
                  file_tag, outlier_max=None, header_extra=""):
    """Driver: capture full-day data, search optimal entry/exit frames per option
    type, print + save results (calls and puts get their own files)."""
    global LOOKBACK_DAYS, DAY_START_M, DAY_END_M
    LOOKBACK_DAYS = lookback_days

    config = Config()
    config.backtest_days = lookback_days
    DAY_START_M = config.window_start_minute
    DAY_END_M = config.window_end_minute
    win_tag = frame_label(DAY_START_M, DAY_END_M).replace(" ", "")

    print(bold("\n" + "═" * 86))
    print(bold(f"  TIME-FRAME BACKTEST  —  {method_label}"))
    print(bold(f"  Lookback window: {lookback_days} calendar days"))
    print(bold(f"  Session window : {frame_label(DAY_START_M, DAY_END_M)} ET "
               "(full regular session)"))
    if header_extra:
        print(f"  {header_extra}")
    print(bold("═" * 86))

    fetcher, source_label = get_fetcher()
    print(f"  Data source: {source_label}")
    print(f"  Tickers: {', '.join(config.tickers)}   "
          f"Option types: {', '.join(opt_word(o) for o in config.option_types)}")
    print(f"  Searching arbitrary entry/exit frames (5 min → full day, "
          f"coarse {COARSE_STEP}-min grid then 1-min refine).\n")

    backtester = Backtester(fetcher, config)
    backtester.run(config.tickers)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    for ticker in config.tickers:
        for opt_type in config.option_types:
            records = backtester.daily_capture.get((ticker, opt_type), [])

            print(bold("\n" + "█" * 86))
            print(bold(f"  {ticker} {opt_word(opt_type)}S"))
            print(bold("█" * 86))

            if len([r for r in records if r["source"] != SOURCE_NO_STOCK]) < MIN_SAMPLES:
                print(red(f"  Not enough data captured for {ticker} "
                          f"{opt_word(opt_type)}s.\n"))
                continue

            res = _analyze(opt_type, records, size_fn, score_key, eligible,
                           outlier_max)

            opt_cell = _optimal_cell(res["frame"])

            def _print_normal():
                print_block(ticker, opt_type, res["frame"], res["rows"], res["summ"])
                print_heatmaps(ticker, opt_type, res["cell_best"], opt_cell)
                print_top_pairs(ticker, opt_type, res["ranked"], res["frame"])

            def _print_excl():
                ex = res["excl"]
                print(bold("\n" + "█" * 86))
                print(bold(f"  OUTLIERS REMOVED (winning trades > ${outlier_max:,.0f})"
                           f"  —  {ticker} {opt_word(opt_type)}S re-optimized"))
                print(bold("█" * 86))
                removed = ex.get("removed") or []
                if removed:
                    print(yellow(f"  (chosen frames dropped {len(removed)} outlier "
                                 f"win(s): {', '.join(removed)})"))
                else:
                    print(yellow("  (chosen frames had no winning outliers)"))
                print_block(ticker, opt_type, ex["frame"], ex["rows"], ex["summ"])
                print_heatmaps(ticker, opt_type, ex["cell_best"],
                               _optimal_cell(ex["frame"]))
                print_top_pairs(ticker, opt_type, ex["ranked"], ex["frame"])

            # Terminal
            _print_normal()
            if outlier_max is not None:
                _print_excl()

            # Capture plain text
            txt_buf = io.StringIO()
            with contextlib.redirect_stdout(txt_buf):
                _print_normal()
                if outlier_max is not None:
                    _print_excl()
            txt_content = txt_buf.getvalue()

            base = (f"backtest_{file_tag}_{opt_tag(opt_type)}_"
                    f"{lookback_days}days_{stamp}")
            csv_path = os.path.join(RESULTS_DIR, f"{base}.csv")
            txt_path = os.path.join(RESULTS_DIR, f"{base}.txt")

            save_csv(opt_type, method_label, header_extra, res["rows"], res["summ"],
                     res["frame"], res["ranked"], source_label, lookback_days,
                     win_tag, csv_path)

            hdr = (f"TIME-FRAME BACKTEST — {method_label} ({opt_word(opt_type)}s)\n"
                   f"Lookback = {lookback_days} calendar days\n"
                   f"Session window = {frame_label(DAY_START_M, DAY_END_M)} ET "
                   "(full regular session)\n"
                   f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
                   f"P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares\n"
                   + "=" * 86 + "\n\n")
            with open(txt_path, "w", encoding="utf-8") as fh:
                fh.write(hdr)
                fh.write(txt_content)

            excl_path = None
            if outlier_max is not None:
                excl_buf = io.StringIO()
                with contextlib.redirect_stdout(excl_buf):
                    _print_excl()
                excl_path = os.path.join(RESULTS_DIR, f"{base}_outliers_removed.txt")
                excl_hdr = (
                    f"TIME-FRAME BACKTEST — {method_label} ({opt_word(opt_type)}s)"
                    f"   [OUTLIERS REMOVED > ${outlier_max:,.0f}]\n"
                    f"Every frame pair re-scored with its winning outlier trades\n"
                    f"(dollar P&L > ${outlier_max:,.0f}) removed, then re-optimized.\n"
                    f"Lookback = {lookback_days} calendar days\n"
                    f"Session window = {frame_label(DAY_START_M, DAY_END_M)} ET\n"
                    f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
                    f"P&L $ assumes 1 contract = {CONTRACT_MULTIPLIER} shares\n"
                    + "=" * 86 + "\n\n")
                with open(excl_path, "w", encoding="utf-8") as fh:
                    fh.write(excl_hdr)
                    fh.write(excl_buf.getvalue())

            print(bold("─" * 86))
            print(f"  {cyan('Saved CSV:')} {bold(csv_path)}")
            print(f"  {cyan('Saved TXT:')} {bold(txt_path)}")
            if excl_path:
                print(f"  {cyan('Saved TXT (outliers removed):')} {bold(excl_path)}")
            print(bold("─" * 86))
            print()
