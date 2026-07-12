"""
core/sequential.py — Mode B: sequential NON-OVERLAPPING trade schedule per day.

HINDSIGHT / OPPORTUNITY COUNTING — not a live rule. It selects entries that DID
reach +T% (first-touch exit), so it answers "how many clean, non-overlapping +T%
moves did this name offer per day," NOT "a rule tradeable in real time." All
output is labelled OPPORTUNITY so it is never mistaken for a backtested edge.

Greedy left-to-right per (symbol, direction, moneyness, fill_mode, T, day):
  1. Keep only 5-min-grid entries whose trade reaches +T% before session close.
  2. cursor = session_open; walk qualifying entries by entry_time ascending; take
     the first with entry_time >= cursor; record it; set cursor = hit_time; repeat.
  3. Entries that never reach +T% are ignored — they never opened a position and
     do NOT block.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def clock(minute: int) -> str:
    minute = int(round(minute))
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _greedy_chain(best: dict, session_open: int) -> list:
    """Greedy non-overlap over {entry_min: (hit_time, minutes_to_hit)}.
    Return list of (entry_min, hit_time, minutes_to_hit)."""
    trades = []
    cursor = session_open
    for e in sorted(best):
        if e >= cursor:
            ht, mins = best[e]
            trades.append((int(e), float(ht), float(mins)))
            cursor = ht
    return trades


def run_mode_b(instances: pd.DataFrame, cfg, session_open: int) -> dict:
    """Return {'trades': DataFrame, 'daily': DataFrame, 'summary': DataFrame}.

    Pure-numpy inner loop: per (symbol, direction, moneyness, fill_mode, date)
    group we pull each threshold's hit/first_hit columns once as arrays, build the
    per-entry fastest hit_time, then greedy-chain — no per-row pandas."""
    if instances.empty:
        empty = pd.DataFrame()
        return {"trades": empty, "daily": empty, "summary": empty}
    thresholds = cfg.thresholds
    keys = ["symbol", "direction", "moneyness", "fill_mode", "date"]
    trade_rows, daily_rows = [], []

    for kv, day_bucket in instances.groupby(keys, sort=False):
        sym, direction, mny, fm, day = kv
        regime = day_bucket["regime"].iloc[0]  # single 0DTE regime per date
        em = day_bucket["entry_min"].to_numpy(dtype=float)
        hit_cols = {T: day_bucket[f"hit@{T}"].to_numpy(dtype=bool) for T in thresholds}
        fh_cols = {T: day_bucket[f"first_hit@{T}"].to_numpy(dtype=float) for T in thresholds}
        for T in thresholds:
            hit = hit_cols[T]
            if not hit.any():
                continue
            fh = fh_cols[T]
            # per entry_min keep the fastest (earliest) hit_time among hitters.
            best = {}
            idx = np.nonzero(hit)[0]
            for i in idx:
                e = em[i]
                ht = e + fh[i]
                cur = best.get(e)
                if cur is None or ht < cur[0]:
                    best[e] = (ht, fh[i])
            chain = _greedy_chain(best, session_open)
            if not chain:
                continue
            for entry_min, hit_time, mins in chain:
                trade_rows.append({
                    "date": day, "symbol": sym, "direction": direction,
                    "moneyness": mny, "fill_mode": fm, "regime": regime,
                    "T_pct": round(T * 100, 4),
                    "entry_time": clock(entry_min), "exit_time": clock(hit_time),
                    "minutes_to_hit": round(mins, 1), "basis": "OPPORTUNITY/HINDSIGHT",
                })
            total_in_pos = sum(ht - em for em, ht, _ in chain)
            drow = {
                "date": day, "symbol": sym, "direction": direction,
                "moneyness": mny, "fill_mode": fm, "regime": regime,
                "T_pct": round(T * 100, 4),
                "n_trades": len(chain), "total_minutes_in_position": round(total_in_pos, 1),
                "basis": "OPPORTUNITY/HINDSIGHT",
            }
            for i in range(3):
                if i < len(chain):
                    e_i, h_i, _ = chain[i]
                    drow[f"trade{i+1}_entry"] = clock(e_i)
                    drow[f"trade{i+1}_exit"] = clock(h_i)
                else:
                    drow[f"trade{i+1}_entry"] = ""
                    drow[f"trade{i+1}_exit"] = ""
            daily_rows.append(drow)

    trades = pd.DataFrame(trade_rows)
    daily = pd.DataFrame(daily_rows)
    summary = _mode_b_summary(daily) if not daily.empty else pd.DataFrame()
    return {"trades": trades, "daily": daily, "summary": summary}


def _to_min(clockstr: str):
    if not clockstr:
        return np.nan
    h, m = clockstr.split(":")
    return int(h) * 60 + int(m)


def _mode_b_summary(daily: pd.DataFrame) -> pd.DataFrame:
    """Per (symbol, direction, moneyness, fill_mode, T): mean & median trades/day,
    share of days with >=1/>=2/>=3 trades, typical clock time of 1st/2nd/3rd entry."""
    keys = ["symbol", "direction", "moneyness", "fill_mode", "regime", "T_pct"]
    rows = []
    for kv, g in daily.groupby(keys, sort=False):
        n_days = len(g)
        nt = g["n_trades"].to_numpy(dtype=float)
        row = dict(zip(keys, kv))
        row.update({
            "n_days": n_days,
            "mean_trades_per_day": round(float(nt.mean()), 3),
            "median_trades_per_day": float(np.median(nt)),
            "share_ge1": round(float((nt >= 1).mean()), 3),
            "share_ge2": round(float((nt >= 2).mean()), 3),
            "share_ge3": round(float((nt >= 3).mean()), 3),
        })
        for i in (1, 2, 3):
            mins = g[f"trade{i}_entry"].map(_to_min).to_numpy(dtype=float)
            mins = mins[np.isfinite(mins)]
            row[f"typ_entry{i}"] = clock(int(np.median(mins))) if mins.size else ""
        rows.append(row)
    return pd.DataFrame(rows)
