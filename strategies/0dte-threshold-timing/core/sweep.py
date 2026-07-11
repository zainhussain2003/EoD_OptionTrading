"""
core/sweep.py — entry sweep → Mode A base-rate surface.

Per contract per session, evaluate candidate entries every `entry_step_min`
minutes from `entry_start_min` to `entry_end_min` ET. For each candidate, build
the mark path from entry to session close and analyze it (both fill modes).
Each candidate entry is a STANDALONE what-if — overlaps are expected and fine in
Mode A; we do NOT deduplicate.

The whole universe runs in ONE pass; results carry `symbol` so everything
downstream splits by symbol rather than being invoked once per ticker.

Output: a tidy DataFrame, one row per (contract-session, entry_minute, fill_mode),
with the grouping keys and the flattened threshold/MFE/MAE metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import Config
from core import expiry as _exp
from core import moneyness as _mny
from core.threshold_timing import analyze_trade


def _minute_of_day(ts: pd.Series) -> pd.Series:
    t = pd.to_datetime(ts)
    return t.dt.hour * 60 + t.dt.minute


def entry_bucket_label(minute: int, bucket_min: int) -> str:
    """Half-open [start, start+bucket) label like '09:30' for the window start."""
    start = (minute // bucket_min) * bucket_min
    return f"{start // 60:02d}:{start % 60:02d}"


def run_sweep(df: pd.DataFrame, cfg: Config) -> tuple:
    """Build the Mode-A instance surface.

    Returns (instances_df, meta) where meta carries the empirical expiry index and
    per-symbol row/instance/bucket counts for the progress line & run_config.
    """
    c = cfg
    df = df.copy()
    df["_date"] = pd.to_datetime(df[c.col_ts]).dt.date
    df["_mod"] = _minute_of_day(df[c.col_ts]).astype(int)
    df[c.col_expiry] = [_exp._as_date(x) for x in df[c.col_expiry]]

    expiry_index = _exp.build_expiry_index(df, c.col_symbol, c.col_expiry, c.col_ts)
    grid = set(c.entry_grid)
    thresholds = c.thresholds

    rows = []
    meta_counts = {}

    for sym, sym_df in df.groupby(c.col_symbol):
        exps = expiry_index.get(sym, [])
        n_rows = len(sym_df)
        n_inst = 0
        buckets = set()

        for trade_date, day_df in sym_df.groupby("_date"):
            tgt = _exp.target_expiry(exps, trade_date)
            if tgt is None:
                continue
            regime, dte, is_0dte = _exp.regime_label(trade_date, tgt)
            day_tgt = day_df[day_df[c.col_expiry] == tgt]
            if day_tgt.empty:
                continue

            # strike increment for this symbol/expiry/day (both rights pooled).
            step = _mny.infer_strike_step(day_tgt[c.col_strike].unique())

            for (right, strike), cs in day_tgt.groupby([c.col_right, c.col_strike]):
                cs = cs.sort_values("_mod")
                minutes = cs["_mod"].to_numpy()
                bid = cs[c.col_bid].to_numpy(dtype=float)
                ask = cs[c.col_ask].to_numpy(dtype=float)
                undr = cs[c.col_underlying].to_numpy(dtype=float)
                # index lookup: minute-of-day → position
                pos = {int(m): i for i, m in enumerate(minutes)}

                for e in c.entry_grid:
                    if e not in pos:
                        continue
                    ei = pos[e]
                    u_e = undr[ei]
                    bucket_m = _mny.classify(u_e, float(strike), str(right), step)
                    ent_bucket = entry_bucket_label(e, c.entry_bucket_min)

                    for fm in c.fill_modes:
                        res = analyze_trade(minutes, bid, ask, ei, thresholds, fm)
                        if res is None:
                            continue
                        row = {
                            c.col_symbol: sym,
                            "direction": "call" if str(right).lower().startswith("c") else "put",
                            "fill_mode": fm,
                            "regime": regime,
                            "dte": dte,
                            "is_0dte": is_0dte,
                            "entry_bucket": ent_bucket,
                            "moneyness": bucket_m,
                            "date": str(trade_date),
                            "strike": float(strike),
                            "expiry": str(tgt),
                            "entry_min": int(e),
                            "underlying_at_entry": float(u_e),
                        }
                        row.update(res)
                        rows.append(row)
                        n_inst += 1
                        buckets.add((row["direction"], fm, regime, ent_bucket, bucket_m))

        meta_counts[sym] = {"rows": n_rows, "instances": n_inst, "buckets": len(buckets)}

    instances = pd.DataFrame(rows)
    meta = {"expiry_index": expiry_index, "counts": meta_counts}
    return instances, meta
