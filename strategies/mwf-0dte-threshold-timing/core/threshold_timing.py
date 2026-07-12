"""
core/threshold_timing.py — the analysis heart.

For ONE trade instance (one contract, one entry minute) compute, over the mark
path from entry to session close:

  first_hit[T]  minutes from entry to the FIRST time the mark reaches +T%
  last_hold[T]  minutes from entry to the LAST time it was still ≥ +T%
  mfe_pct/min   peak favorable excursion and when it occurred
  mae_pct/min   worst adverse excursion and when it occurred

Two fill modes, run BOTH:
  mid    : mark = (bid+ask)/2, entry at mid.  pct[t] = mid[t]/mid[e] − 1
  market : open at ask, close at bid.         pct[t] = bid[t]/ask[e] − 1
           (every trade starts ≈ −spread%; the number we trust.)

No-lookahead is structural: an instance only ever sees bars at/after its own
entry minute — callers slice the path at `entry_idx` and we never index before it.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


# ── one instance ────────────────────────────────────────────────────────────
def pct_path(minutes: np.ndarray, bid: np.ndarray, ask: np.ndarray,
             entry_idx: int, fill_mode: str) -> Optional[tuple]:
    """Return (rel_minutes, pct) for the path from entry to close, or None if the
    entry minute has no valid quote.

    rel_minutes[k] = minutes[entry_idx + k] − minutes[entry_idx]  (>= 0, no lookahead)
    pct[k]         = fractional return of the mark vs the entry cost.
    """
    b_e = bid[entry_idx]
    a_e = ask[entry_idx]
    # Skip contracts with no valid quote at the entry minute (bid/ask NaN or ask<=0).
    if not np.isfinite(a_e) or a_e <= 0 or not np.isfinite(b_e) or b_e < 0:
        return None

    m = minutes[entry_idx:]
    b = bid[entry_idx:]
    a = ask[entry_idx:]
    rel = (m - minutes[entry_idx]).astype(float)

    if fill_mode == "mid":
        mid_e = 0.5 * (b_e + a_e)
        if mid_e <= 0:
            return None
        mark = 0.5 * (b + a)
        pct = mark / mid_e - 1.0
    elif fill_mode == "market":
        # long-option realism: pay the ask on entry, receive the bid on exit.
        pct = b / a_e - 1.0
    else:
        raise ValueError(f"unknown fill_mode {fill_mode!r}")

    return rel, pct


def analyze_trade(minutes: np.ndarray, bid: np.ndarray, ask: np.ndarray,
                  entry_idx: int, thresholds: list, fill_mode: str) -> Optional[dict]:
    """Compute first_hit/last_hold per threshold + MFE/MAE for one instance.

    `minutes` are ET minute-of-day ints (ascending), `bid`/`ask` are aligned
    arrays for the SAME contract-session. `entry_idx` indexes into them.
    Returns a dict, or None when the entry minute is unquotable.
    """
    got = pct_path(minutes, bid, ask, entry_idx, fill_mode)
    if got is None:
        return None
    rel, pct = got
    if pct.size == 0:
        return None

    # Guard against all-NaN paths (e.g. a contract that stops quoting immediately).
    valid = np.isfinite(pct)
    if not valid.any():
        return None
    rel_v = rel[valid]
    pct_v = pct[valid]

    out = {"entry_pct": float(pct_v[0])}

    # Forced-exit reference: the mark at the LAST available bar of the session
    # (Mode C's default MAX_EXIT_TIME = session close / 0DTE expiry). Recorded so
    # a non-hit's realized return can be read off without re-walking the path.
    out["close_pct"] = float(pct_v[-1])
    out["close_min"] = float(rel_v[-1])

    # MFE / MAE over the whole forward path.
    i_max = int(np.argmax(pct_v))
    i_min = int(np.argmin(pct_v))
    out["mfe_pct"] = float(pct_v[i_max])
    out["mfe_min"] = float(rel_v[i_max])
    out["mae_pct"] = float(pct_v[i_min])
    out["mae_min"] = float(rel_v[i_min])

    # Threshold ladder.
    for T in thresholds:
        at_or_above = pct_v >= T
        if at_or_above.any():
            idx = np.nonzero(at_or_above)[0]
            out[f"first_hit@{T}"] = float(rel_v[idx[0]])
            out[f"last_hold@{T}"] = float(rel_v[idx[-1]])
            out[f"hit@{T}"] = True
        else:
            out[f"first_hit@{T}"] = np.nan
            out[f"last_hold@{T}"] = np.nan
            out[f"hit@{T}"] = False

    return out
