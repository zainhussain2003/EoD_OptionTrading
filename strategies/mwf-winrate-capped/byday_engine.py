#!/usr/bin/env python3
"""
BY-DAY SCORING ENGINE  (compact, window-parametrized)

The pure-computation core shared by backtest_byday.py (terminal report) and
strategy.py (pipeline adapter). It mirrors the proven calls/puts backtest_engine
building blocks — build_representatives, compute_pair_stats, find_optimal_pair,
per_day_pnl, summarize — but takes the trading window explicitly (no module
globals) so each weekday can be scored on its own window.

It contains NO option-type or data-fetch logic: it consumes the records the
unified Backtester captured (keyed by (ticker, opt_type)) and returns stats /
rows / summaries. Selection policy (scoring + the win-rate cap) is supplied by
the caller via score_key / eligible, exactly like the original engine.
"""
from collections import defaultdict

from models import SOURCE_REAL, SOURCE_NO_STOCK
from utils.date_utils import minute_to_str

# 1 option contract controls 100 shares — payoff/share × 100 = dollars/contract.
CONTRACT_MULTIPLIER = 100

ENTRY_STEP = 5
MIN_HOLD = 5
MIN_SAMPLES = 3            # statistical floor: a pair needs >= 3 dates to count


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
        rep = min(pool, key=lambda r: abs(r["strike"] - r["spot_open"]))
        reps[d] = rep["prices"]
        meta[d] = rep
    return reps, meta


def compute_pair_stats(reps: dict, win_start_m: int, win_end_m: int,
                       size_fn=None) -> dict:
    """Stats for EVERY (entry, exit) pair across all dates in the window.

    Returns {(entry_m, exit_m): {entry, exit, wins, n, wr, avg, total}} where
    avg/total are per-share (× CONTRACT_MULTIPLIER for dollars per contract).
    size_fn(entry_price) -> int contracts scales each date's payoff (wins are
    unaffected — the scale factor is always positive). Default None = 1 contract.
    """
    payoffs = defaultdict(list)
    for d, prices in reps.items():
        for entry_m in range(win_start_m, win_end_m - MIN_HOLD, ENTRY_STEP):
            ep, em = price_at(prices, entry_m)
            if ep is None or ep <= 0:
                continue
            qty = size_fn(ep) if size_fn else 1
            for exit_m in range(entry_m + MIN_HOLD, win_end_m, ENTRY_STEP):
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

    score_key(stat) -> sortable key (higher = better)
    eligible(stat)  -> bool (whether the pair may be chosen at all)
    Returns (best_stat | None, ranked_eligible_list).
    """
    elig = [s for s in stats.values() if eligible(s)]
    if not elig:
        return None, []
    ranked = sorted(elig, key=score_key, reverse=True)
    return ranked[0], ranked


def per_day_pnl(ticker: str, opt_type: str, reps: dict, meta: dict,
                entry_m: int, exit_m: int, size_fn=None) -> list:
    """One row per date: the ATM option bought at entry_m, sold at exit_m."""
    rows = []
    for d in sorted(reps.keys()):
        prices = reps[d]
        rec = meta[d]
        ep, em = price_at(prices, entry_m)
        xp, xm = price_at(prices, exit_m, after=em)

        if ep is None or xp is None or ep <= 0:
            if rec.get("source") == SOURCE_NO_STOCK:
                skip_src, skip_note = "MISS", rec.get("note") or "missing data"
            else:
                skip_src = "REAL" if rec["source"] == SOURCE_REAL else "SIM"
                skip_note = "no usable price at entry/exit"
            rows.append({
                "date": str(d), "ticker": ticker, "opt_type": opt_type,
                "contract_symbol": rec["contract"], "strike": rec["strike"],
                "source": skip_src,
                "entry_time": minute_to_str(entry_m), "entry_price": "",
                "exit_time": minute_to_str(exit_m), "exit_price": "",
                "payoff_per_share": "", "contracts": "", "cost_dollars": "",
                "pnl_dollars": "", "profitable": "", "note": skip_note,
            })
            continue

        qty = size_fn(ep) if size_fn else 1
        payoff = xp - ep
        rows.append({
            "date": str(d), "ticker": ticker, "opt_type": opt_type,
            "contract_symbol": rec["contract"], "strike": rec["strike"],
            "source": "REAL" if rec["source"] == SOURCE_REAL else "SIM",
            "entry_time": minute_to_str(em), "entry_price": round(ep, 4),
            "exit_time": minute_to_str(xm), "exit_price": round(xp, 4),
            "payoff_per_share": round(payoff, 4),
            "contracts": qty,
            "cost_dollars": round(ep * CONTRACT_MULTIPLIER * qty, 2),
            "pnl_dollars": round(payoff * CONTRACT_MULTIPLIER * qty, 2),
            "profitable": payoff > 0, "note": rec.get("note", ""),
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
