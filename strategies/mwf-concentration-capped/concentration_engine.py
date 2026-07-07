#!/usr/bin/env python3
"""
CONCENTRATION-CAPPED time-schedule engine (Mon / Wed / Fri, calls + puts).

For each (ticker, weekday, option type) this searches every fixed 5-minute
(entry_time, exit_time) schedule inside that day's trading window — exactly the
sized by-day backtests' model — and ranks the schedules by

    score = win_rate × avg_payoff          (max expected profit)

Position sizing is target-spend, identical to the sized backtests:

    contracts = ceil(TARGET_SPEND / entry_price), minimum 1

so every P&L below is the per-share move × contracts (multiply by
CONTRACT_MULTIPLIER for dollars).

THE CONCENTRATION CAP (replaces the old outlier system)
───────────────────────────────────────────────────────
A schedule is only ELIGIBLE to be chosen as "best" if no single winning trade
dominates its total return over the lookback:

    single_trade_share = (largest single winning trade P&L) / (net total P&L)
    eligible  ⇔  net_total_pnl > 0  AND  single_trade_share <= MAX_SINGLE_TRADE_SHARE

If net_total_pnl <= 0 the schedule is ineligible (share undefined); a schedule
with no winning trades is ineligible. The cap only decides eligibility — the
ranking metric (win_rate × avg_payoff) is unchanged. There is NO outlier
dollar-drop pass: the largest single winning trade and the total are both taken
from the SAME sized dollar P&L, so the share is a pure share of the real total.
"""

from collections import defaultdict

from models import SOURCE_REAL, SOURCE_NO_STOCK
from utils.date_utils import minute_to_str

# 1 option contract controls 100 shares — payoff per share × 100 = dollars/contract.
CONTRACT_MULTIPLIER = 100

ENTRY_STEP = 5            # 5-minute entry/exit grid
MIN_HOLD = 5             # a trade must be held at least one step
MIN_SAMPLES = 3          # a schedule needs >= 3 dates to count


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


def compute_pair_stats(reps: dict, start_m: int, end_m: int, size_fn=None) -> dict:
    """Stats for EVERY (entry, exit) schedule across all dates in one window.

    Returns {(entry_m, exit_m): stat} where stat carries, per schedule:
        wins, n, wr, avg, total   — win rate + per-share-sized aggregates
        max_win                   — the LARGEST single winning trade's P&L
                                    (same per-share-sized units as total; None
                                    if the schedule has no winning trade)
        single_trade_share        — max_win / total when total > 0 and a win
                                    exists, else None. This is what the cap tests.

    Retaining max_win (rather than only aggregates, as the sized engine did) is
    what lets the concentration cap decide eligibility without a separate pass.
    """
    payoffs = defaultdict(list)
    for d, prices in reps.items():
        for entry_m in range(start_m, end_m - MIN_HOLD, ENTRY_STEP):
            ep, em = price_at(prices, entry_m)
            if ep is None or ep <= 0:
                continue
            qty = size_fn(ep) if size_fn else 1
            for exit_m in range(entry_m + MIN_HOLD, end_m, ENTRY_STEP):
                xp, _ = price_at(prices, exit_m, after=em)
                if xp is None:
                    continue
                payoffs[(entry_m, exit_m)].append((xp - ep) * qty)

    stats = {}
    for (en, ex), pl in payoffs.items():
        if len(pl) < MIN_SAMPLES:
            continue
        wins_list = [p for p in pl if p > 0]
        wins = len(wins_list)
        total = sum(pl)
        max_win = max(wins_list) if wins_list else None
        share = (max_win / total) if (max_win is not None and total > 0) else None
        stats[(en, ex)] = {
            "entry": en, "exit": ex, "wins": wins, "n": len(pl),
            "wr": wins / len(pl), "avg": total / len(pl), "total": total,
            "max_win": max_win, "single_trade_share": share,
        }
    return stats


def find_optimal_pair(stats: dict, score_key, eligible):
    """Pick the best (entry, exit) using the caller's scoring + eligibility.

    score_key(stat) -> sortable key (higher = better)
    eligible(stat)  -> bool (the concentration cap lives here)
    Returns (best_stat | None, ranked_eligible_list).
    """
    elig = [s for s in stats.values() if eligible(s)]
    if not elig:
        return None, []
    ranked = sorted(elig, key=score_key, reverse=True)
    return ranked[0], ranked


def per_day_pnl(ticker: str, reps: dict, meta: dict, entry_m: int, exit_m: int,
                size_fn=None) -> list:
    """One row per date: the ATM option bought at entry_m, sold at exit_m."""
    rows = []
    for d in sorted(reps.keys()):
        prices = reps[d]
        rec = meta[d]
        ep, em = price_at(prices, entry_m)
        xp, xm = price_at(prices, exit_m, after=em)

        if ep is None or xp is None or ep <= 0:
            if rec.get("source") == SOURCE_NO_STOCK:
                skip_src = "MISS"
                skip_note = rec.get("note") or "missing data (market closed)"
            else:
                skip_src = "REAL" if rec["source"] == SOURCE_REAL else "SIM"
                skip_note = "no usable price at entry/exit"
            rows.append({
                "date": str(d), "ticker": ticker,
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
            "date": str(d), "ticker": ticker,
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


def opt_word(opt_type: str) -> str:
    return "CALL" if opt_type == 'C' else "PUT"
