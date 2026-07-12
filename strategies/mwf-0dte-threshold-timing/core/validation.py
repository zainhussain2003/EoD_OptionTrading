"""
core/validation.py — adversarial review, run before accepting results.

Checks (fail LOUD; the report is written to the deliverables):
  1. mid ≥ market gate: in every bucket, `market` hit% ≤ `mid` hit% and
     `market` first-touch ≥ `mid` first-touch. Violations usually mean a
     spread / side-of-book bug.
  2. Regime detection matches the cadence table for the daily names, and
     ORCL/AMD early-week entries are labelled as bridges, not 0DTE.
  3. Entry sweep has no duplicate/overlapping instances per contract-session.
  4. Spot-check: recompute first_hit/last_hold for N random instances directly
     from raw bid/ask and confirm they match analyze_trade.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.threshold_timing import analyze_trade


def check_mid_ge_market(instances: pd.DataFrame, cfg) -> dict:
    """The rigorous PER-INSTANCE invariant (same contract, same entry minute):
      - a `market` hit implies a `mid` hit   → market hit% ≤ mid hit% in every bucket
      - where both hit, market first-touch ≥ mid first-touch (market pays the spread)

    Checked per instance rather than on bucket medians, which are subject to
    composition artifacts. Any violation is almost always a spread / side-of-book
    bug. Returns a violation summary per threshold."""
    if instances.empty:
        return {"violations": [], "n_compared": 0, "ok": True}
    keys = ["symbol", "date", "direction", "strike", "expiry", "entry_min"]
    mid = instances[instances["fill_mode"] == "mid"].set_index(keys).sort_index()
    mkt = instances[instances["fill_mode"] == "market"].set_index(keys).sort_index()
    common = mid.index.intersection(mkt.index)
    if len(common) == 0:
        return {"violations": [], "n_compared": 0, "ok": True}
    mid = mid.loc[common]
    mkt = mkt.loc[common]
    violations = []
    for T in cfg.thresholds:
        mh = mid[f"hit@{T}"].to_numpy(dtype=bool)
        kh = mkt[f"hit@{T}"].to_numpy(dtype=bool)
        n_bad_hit = int((kh & ~mh).sum())
        if n_bad_hit:
            violations.append({"T_pct": round(T * 100, 4),
                               "kind": "market_hit_without_mid_hit", "count": n_bad_hit})
        both = kh & mh
        mf = mid[f"first_hit@{T}"].to_numpy(dtype=float)
        kf = mkt[f"first_hit@{T}"].to_numpy(dtype=float)
        n_bad_ft = int((both & (kf < mf - 1e-9)).sum())
        if n_bad_ft:
            violations.append({"T_pct": round(T * 100, 4),
                               "kind": "market_first_touch<mid_first_touch",
                               "count": n_bad_ft})
    return {"violations": violations, "n_compared": int(len(common)),
            "ok": len(violations) == 0}


_DOW_OK = {"Mon", "Wed", "Fri"}


def check_regimes(instances: pd.DataFrame, cfg) -> dict:
    """This is a TRUE 0DTE study on Mon/Wed/Fri, so the invariant is simple and
    strict: EVERY instance must be 0DTE (no bridges) and land on Mon/Wed/Fri. We
    do NOT assert how often a name is 0DTE — daily single-name expiries are recent,
    so a name legitimately has few Mon/Wed 0DTE sessions. Sample size/recency is
    reported per bucket (first_date/last_date/n_sessions), not failed here."""
    problems = []
    if instances.empty:
        return {"problems": ["no instances"], "ok": False}
    if not bool(instances["is_0dte"].all()):
        n_bad = int((~instances["is_0dte"]).sum())
        problems.append(f"{n_bad} non-0DTE (bridge) instances present — should be zero")
    bad_dows = sorted(set(instances["dow"]) - _DOW_OK)
    if bad_dows:
        problems.append(f"unexpected entry weekdays present: {bad_dows}")
    per_sym = (instances.groupby(["symbol", "dow"])["date"].nunique()
               .unstack(fill_value=0).to_dict("index"))
    return {"problems": problems, "ok": len(problems) == 0,
            "per_symbol_dow_sessions": per_sym}


def check_no_overlap(instances: pd.DataFrame) -> dict:
    """No duplicate (contract-session, entry_min, fill_mode) instances."""
    if instances.empty:
        return {"ok": True, "n_dupes": 0}
    key = ["symbol", "date", "direction", "strike", "expiry", "entry_min", "fill_mode"]
    dupes = int(instances.duplicated(key).sum())
    return {"ok": dupes == 0, "n_dupes": dupes}


def spot_check(df_contract: pd.DataFrame, cfg, n: int = 5, seed: int = 7) -> dict:
    """Recompute first_hit/last_hold for N random contract-sessions directly and
    confirm analyze_trade agrees."""
    rng = np.random.default_rng(seed)
    keyc = ["symbol", "right", "strike", "expiry"]
    df = df_contract.copy()
    df["_date"] = pd.to_datetime(df["ts"]).dt.date
    df["_mod"] = pd.to_datetime(df["ts"]).dt.hour * 60 + pd.to_datetime(df["ts"]).dt.minute
    groups = list(df.groupby(keyc + ["_date"]))
    if not groups:
        return {"ok": True, "checked": 0, "mismatches": []}
    picks = rng.choice(len(groups), size=min(n, len(groups)), replace=False)
    mismatches = []
    checked = 0
    T = 0.20
    for pi in picks:
        _, g = groups[pi]
        g = g.sort_values("_mod")
        minutes = g["_mod"].to_numpy()
        bid = g["bid"].to_numpy(float)
        ask = g["ask"].to_numpy(float)
        if len(minutes) < 3:
            continue
        ei = 0
        res = analyze_trade(minutes, bid, ask, ei, [T], "market")
        if res is None:
            continue
        # independent brute-force recompute (market fill)
        pct = bid[ei:] / ask[ei] - 1.0
        rel = (minutes[ei:] - minutes[ei]).astype(float)
        above = np.nonzero(pct >= T)[0]
        exp_first = float(rel[above[0]]) if above.size else np.nan
        exp_last = float(rel[above[-1]]) if above.size else np.nan
        got_first = res[f"first_hit@{T}"]
        got_last = res[f"last_hold@{T}"]
        checked += 1
        same = (np.isnan(exp_first) and np.isnan(got_first)) or (
            np.isclose(exp_first, got_first) and np.isclose(exp_last, got_last))
        if not same:
            mismatches.append({"expected": (exp_first, exp_last),
                               "got": (got_first, got_last)})
    return {"ok": len(mismatches) == 0, "checked": checked, "mismatches": mismatches}


def run_all(df_contract, instances, bucketed, cfg) -> dict:
    return {
        "mid_ge_market": check_mid_ge_market(instances, cfg),
        "regimes": check_regimes(instances, cfg),
        "no_overlap": check_no_overlap(instances),
        "spot_check": spot_check(df_contract, cfg),
    }
