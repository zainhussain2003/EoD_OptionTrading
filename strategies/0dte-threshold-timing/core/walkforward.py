"""
core/walkforward.py — Mode C: optimized, chained, forced-exit strategy.

The TRADEABLE version, evaluated WALK-FORWARD so the entry schedule is never
curve-fit:

  1. Roll train→test windows across the date range (default train 6wk / test 2wk,
     rolling; expanding-window optional). ~5 sessions per week.
  2. On TRAIN only, rank entry windows by hit-probability of +T% (core.optimizer).
     Freeze the ranked schedule — it never sees a test day.
  3. On each TEST day, chain non-overlapping: enter at the start of the
     top-ranked eligible window; exit at first-touch of +T% (realized +T%) or, if
     not reached by MAX_EXIT_TIME, forced-exit at the prevailing mark; advance the
     cursor to the exit and take the next-highest-ranked window starting >= cursor.
  4. KEEP non-hit / forced-exit trades — dropping them recreates Mode B's hindsight
     bias and fakes the edge.

MAX_EXIT_TIME default = session close (close_pct). Non-default rules require the
full path and are rejected loudly rather than silently approximated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.optimizer import rank_windows_for
from core.sequential import clock


class LeakageError(AssertionError):
    pass


def make_folds(dates: list, train_weeks: int, test_weeks: int, expanding: bool) -> list:
    """Roll (train_dates, test_dates) folds over sorted session dates.
    Weeks are approximated as 5 trading sessions."""
    d = sorted(dates)
    tr = train_weeks * 5
    te = test_weeks * 5
    folds = []
    start = 0
    while True:
        tr_end = start + tr
        te_end = tr_end + te
        if tr_end >= len(d) or tr_end == te_end:
            break
        train = d[0:tr_end] if expanding else d[start:tr_end]
        test = d[tr_end:min(te_end, len(d))]
        if not test:
            break
        folds.append((train, test))
        if te_end >= len(d):
            break
        start += te
    return folds


def _entry_minute_for(start_min: int, grid: list):
    """Earliest 5-min grid minute >= a window's start (the 'start of the window')."""
    for g in grid:
        if g >= start_min:
            return g
    return None


def _day_lookup(sub: pd.DataFrame) -> dict:
    """Precompute {date: {entry_min: representative row-dict}} for a
    (symbol, direction, moneyness, fill_mode) slice. Representative = the median
    strike among the moneyness bucket's rows at that entry minute (deterministic,
    T-independent), so it is built once and reused across thresholds."""
    out = {}
    for d, g in sub.groupby("date", sort=False):
        m = {}
        for emin, gg in g.groupby("entry_min", sort=False):
            ggs = gg.sort_values("strike")
            m[int(emin)] = ggs.iloc[len(ggs) // 2].to_dict()
        out[d] = m
    return out


def _chain_test_day(day_map, ranked, session_open, grid, T, max_exit_min):
    """Walk one test session; return list of trade dicts."""
    trades = []
    remaining = list(ranked)  # best→worst
    cursor = session_open
    while True:
        pick = None
        for i, w in enumerate(remaining):
            emin = _entry_minute_for(int(w["start_min"]), grid)
            if emin is not None and emin >= cursor:
                pick = (i, emin, w)
                break
        if pick is None:
            break
        i, emin, w = pick
        remaining.pop(i)
        inst = day_map.get(emin)
        if inst is None:
            continue  # no quote for that window this day; window consumed, move on
        hit = bool(inst[f"hit@{T}"])
        if hit:
            exit_rel = float(inst[f"first_hit@{T}"])
            exit_min = emin + exit_rel
            if exit_min > max_exit_min:
                # target only counts if reached by MAX_EXIT_TIME.
                hit = False
        if hit:
            realized = T
            exit_reason = "target"
        else:
            realized = float(inst["close_pct"])  # forced exit at session close
            exit_min = min(emin + float(inst["close_min"]), max_exit_min)
            exit_reason = "forced"
        trades.append({
            "entry_min": emin, "exit_min": exit_min,
            "exit_reason": exit_reason, "realized_return": realized,
        })
        cursor = exit_min
    return trades


def run_mode_c(instances: pd.DataFrame, cfg, session_open: int) -> dict:
    """Return {'trades': DataFrame, 'perf': DataFrame}."""
    if instances.empty:
        return {"trades": pd.DataFrame(), "perf": pd.DataFrame()}

    rule, rule_arg = cfg.max_exit_rule
    if rule != "session_close":
        raise NotImplementedError(
            f"max_exit_rule={cfg.max_exit_rule!r}: only 'session_close' is supported "
            "from the instance surface; other rules need the full mark path."
        )
    max_exit_min = cfg.session_close_min
    grid = cfg.entry_grid
    thresholds = cfg.thresholds

    combo_keys = ["symbol", "direction", "moneyness", "fill_mode"]
    trade_rows, perf_rows = [], []

    for kv, sub in instances.groupby(combo_keys, sort=False):
        sym, direction, mny, fm = kv
        dates = sorted(sub["date"].unique())
        folds = make_folds(dates, cfg.train_weeks, cfg.test_weeks, cfg.expanding_window)
        if not folds:
            continue
        by_date = _day_lookup(sub)

        for T in thresholds:
            realized_all, hit_all = [], []
            test_days_used = set()
            for train_dates, test_dates in folds:
                # Leakage guard — the schedule must never see a test day.
                if set(train_dates) & set(test_dates):
                    raise LeakageError(
                        f"train/test overlap for {sym}/{direction}/{mny}/{fm} T={T}"
                    )
                train_df = sub[sub["date"].isin(train_dates)]
                ranked = rank_windows_for(train_df, sym, direction, mny, fm, T)
                if not ranked:
                    continue
                for d in test_dates:
                    day_rows = by_date.get(d)
                    if day_rows is None:
                        continue
                    tr = _chain_test_day(day_rows, ranked, session_open, grid, T,
                                         max_exit_min)
                    test_days_used.add(d)
                    for t in tr:
                        realized_all.append(t["realized_return"])
                        hit_all.append(t["exit_reason"] == "target")
                        trade_rows.append({
                            "date": d, "symbol": sym, "direction": direction,
                            "moneyness": mny, "fill_mode": fm, "T_pct": round(T * 100, 4),
                            "entry_time": clock(t["entry_min"]), "exit_time": clock(t["exit_min"]),
                            "exit_reason": t["exit_reason"],
                            "realized_return": round(t["realized_return"], 5),
                        })

            n_tr = len(realized_all)
            if n_tr == 0:
                continue
            realized = np.array(realized_all, dtype=float)
            hits = np.array(hit_all, dtype=bool)
            n_test_days = max(len(test_days_used), 1)
            wins = realized[hits]
            losses = realized[~hits]
            perf_rows.append({
                "symbol": sym, "direction": direction, "moneyness": mny,
                "fill_mode": fm, "T_pct": round(T * 100, 4),
                "n_test_trades": n_tr,
                "n_test_days": n_test_days,
                "trades_per_day": round(n_tr / n_test_days, 3),
                "win_rate": round(float(hits.mean()), 4),
                "avg_win": round(float(wins.mean()), 5) if wins.size else np.nan,
                "avg_loss": round(float(losses.mean()), 5) if losses.size else np.nan,
                "expectancy_per_trade": round(float(realized.mean()), 5),
                "expectancy_per_day": round(float(realized.sum() / n_test_days), 5),
                "cumulative_test_pnl": round(float(realized.sum()), 5),
                "unreliable_low_sample": bool(n_tr < cfg.min_test_trades),
            })

    return {"trades": pd.DataFrame(trade_rows), "perf": pd.DataFrame(perf_rows)}
