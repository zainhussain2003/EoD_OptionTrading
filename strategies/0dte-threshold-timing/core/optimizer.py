"""
core/optimizer.py — entry-window ranker (adapted to rank on HIT-PROBABILITY).

The repo's existing optimizers (calls/ , puts/) rank entry×exit MINUTE PAIRS by
`win_rate × avg_payoff`. That is the wrong objective here and it optimizes the
exit too. This ranker is adapted to the narrow job Modes A–C need:

  rank ENTRY time-of-day windows by the probability of reaching a given
  threshold +T%, per (symbol, direction, moneyness[, regime]); the EXIT is the
  threshold / forced-exit rule, not something the optimizer picks.

It runs over the whole universe in one pass and groups by symbol — never invoked
once per ticker. `rank_windows_for` is train-only and is what Mode C freezes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def bucket_start_min(label: str) -> int:
    h, m = label.split(":")
    return int(h) * 60 + int(m)


def _window_stats(g: pd.DataFrame, T: float) -> dict:
    hit = g[f"hit@{T}"].to_numpy(dtype=bool)
    fh = g[f"first_hit@{T}"].to_numpy(dtype=float)
    fh = fh[np.isfinite(fh)]
    return {
        "n": len(g),
        "hit_pct": 100.0 * hit.mean() if len(g) else np.nan,
        "median_min_to_target": float(np.median(fh)) if fh.size else np.nan,
    }


def optimal_entry_surface(instances: pd.DataFrame, cfg) -> pd.DataFrame:
    """Deliverable `optimal_entry.csv`: for each target in
    cfg.optimal_entry_targets_pct, ranked entry windows per
    (symbol, direction, regime, fill_mode), with median minutes-to-target.

    Rank is 1 = highest hit%. `market` rows are the ones to trust; both fill
    modes are emitted so the mid-vs-market gap is visible.
    """
    if instances.empty:
        return pd.DataFrame()
    targets = [t / 100.0 for t in cfg.optimal_entry_targets_pct]
    keys = ["symbol", "direction", "regime", "fill_mode"]
    rows = []
    for kv, g in instances.groupby(keys, sort=False):
        base = dict(zip(keys, kv))
        for T in targets:
            recs = []
            for bucket, gb in g.groupby("entry_bucket", sort=False):
                st = _window_stats(gb, T)
                recs.append({"entry_bucket": bucket, **st})
            rdf = pd.DataFrame(recs)
            # rank by hit% desc, then earlier median-to-target, then earlier clock.
            rdf["_bstart"] = rdf["entry_bucket"].map(bucket_start_min)
            rdf = rdf.sort_values(
                ["hit_pct", "median_min_to_target", "_bstart"],
                ascending=[False, True, True], kind="mergesort",
            ).reset_index(drop=True)
            rdf["rank"] = np.arange(1, len(rdf) + 1)
            for _, r in rdf.iterrows():
                rows.append({
                    **base,
                    "T_pct": round(T * 100, 4),
                    "rank": int(r["rank"]),
                    "entry_bucket": r["entry_bucket"],
                    "n": int(r["n"]),
                    "hit_pct": round(r["hit_pct"], 3),
                    "median_min_to_target": r["median_min_to_target"],
                    "low_sample": bool(r["n"] < cfg.min_bucket_n),
                })
    return pd.DataFrame(rows)


def rank_windows_for(train: pd.DataFrame, symbol: str, direction: str,
                     moneyness: str, fill_mode: str, T: float) -> list:
    """TRAIN-ONLY ranked entry schedule for Mode C.

    Returns a list of dicts [{entry_bucket, start_min, hit_pct, n, median_min}]
    ordered best→worst by hit-probability of +T% for that exact
    (symbol, direction, moneyness, fill_mode). This is frozen and applied to the
    test window; it must never see a test day.
    """
    g = train[
        (train["symbol"] == symbol)
        & (train["direction"] == direction)
        & (train["moneyness"] == moneyness)
        & (train["fill_mode"] == fill_mode)
    ]
    if g.empty:
        return []
    recs = []
    for bucket, gb in g.groupby("entry_bucket", sort=False):
        st = _window_stats(gb, T)
        recs.append({
            "entry_bucket": bucket,
            "start_min": bucket_start_min(bucket),
            "hit_pct": st["hit_pct"],
            "n": st["n"],
            "median_min": st["median_min_to_target"],
        })
    rdf = pd.DataFrame(recs).sort_values(
        ["hit_pct", "median_min", "start_min"],
        ascending=[False, True, True], kind="mergesort",
    )
    return rdf.to_dict("records")
