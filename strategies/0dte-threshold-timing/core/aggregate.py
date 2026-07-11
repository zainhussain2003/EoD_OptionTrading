"""
core/aggregate.py — bucketed base-rate tables from the Mode-A surface.

Grouping keys: symbol, direction, fill_mode, regime, entry_bucket, moneyness.
Per bucket, per threshold T report:
  n, hit%[T], median + IQR first_hit[T], median last_hold[T],
  median mfe_pct, median mfe_min (typical peak timing), median mae_pct.

Also a coarser (symbol, direction, fill_mode, dow) roll-up.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import Config

GROUP_KEYS = ["symbol", "direction", "fill_mode", "regime", "entry_bucket", "moneyness"]


def _dow_from_regime(regime: str) -> str:
    # "Fri-0DTE" → "Fri"; "Mon->Fri" → "Mon" (entry DOW)
    return regime.split("-")[0].split("->")[0]


def _q(a, p):
    a = a[np.isfinite(a)]
    return float(np.quantile(a, p)) if a.size else np.nan


def _bucket_threshold_stats(g: pd.DataFrame, thresholds, symbol_col) -> list:
    """One block of rows (one per T) for a single bucket group `g`."""
    out = []
    n = len(g)
    mfe_pct = g["mfe_pct"].to_numpy(dtype=float)
    mfe_min = g["mfe_min"].to_numpy(dtype=float)
    mae_pct = g["mae_pct"].to_numpy(dtype=float)
    for T in thresholds:
        hit = g[f"hit@{T}"].to_numpy(dtype=bool)
        fh = g[f"first_hit@{T}"].to_numpy(dtype=float)
        lh = g[f"last_hold@{T}"].to_numpy(dtype=float)
        out.append({
            "T_pct": round(T * 100, 4),
            "n": n,
            "hit_pct": round(100.0 * hit.mean(), 3) if n else np.nan,
            "first_hit_median": _q(fh, 0.5),
            "first_hit_q25": _q(fh, 0.25),
            "first_hit_q75": _q(fh, 0.75),
            "last_hold_median": _q(lh, 0.5),
            "mfe_pct_median": round(_q(mfe_pct, 0.5), 5),
            "mfe_min_median": _q(mfe_min, 0.5),
            "mae_pct_median": round(_q(mae_pct, 0.5), 5),
        })
    return out


def bucketed_table(instances: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Full bucketed base-rate table across the universe (one row per bucket×T)."""
    if instances.empty:
        return pd.DataFrame()
    thresholds = cfg.thresholds
    rows = []
    for keys, g in instances.groupby(GROUP_KEYS, sort=False):
        base = dict(zip(GROUP_KEYS, keys))
        for block in _bucket_threshold_stats(g, thresholds, "symbol"):
            r = dict(base)
            r.update(block)
            r["low_sample"] = bool(r["n"] < cfg.min_bucket_n)
            rows.append(r)
    out = pd.DataFrame(rows)
    return out


def dow_rollup(instances: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Coarser (symbol, direction, fill_mode, dow) roll-up."""
    if instances.empty:
        return pd.DataFrame()
    df = instances.copy()
    df["dow"] = df["regime"].map(_dow_from_regime)
    thresholds = cfg.thresholds
    rows = []
    for keys, g in df.groupby(["symbol", "direction", "fill_mode", "dow"], sort=False):
        base = dict(zip(["symbol", "direction", "fill_mode", "dow"], keys))
        n = len(g)
        for T in thresholds:
            hit = g[f"hit@{T}"].to_numpy(dtype=bool)
            fh = g[f"first_hit@{T}"].to_numpy(dtype=float)
            r = dict(base)
            r.update({
                "T_pct": round(T * 100, 4),
                "n": n,
                "hit_pct": round(100.0 * hit.mean(), 3) if n else np.nan,
                "first_hit_median": _q(fh, 0.5),
                "low_sample": bool(n < cfg.min_bucket_n),
            })
            rows.append(r)
    return pd.DataFrame(rows)
