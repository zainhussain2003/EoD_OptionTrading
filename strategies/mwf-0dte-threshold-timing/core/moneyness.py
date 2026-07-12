"""
core/moneyness.py — ITM / ATM / OTM1 / OTM2+ classification.

Bucketing is from underlying-vs-strike AT ENTRY, measured in strike increments
(the increment is inferred from the strikes actually present for that
symbol/expiry, since it varies by name and price). "OTM distance" is signed so
the same rule serves calls and puts:

  call: OTM when strike > underlying → otm = strike − underlying
  put : OTM when strike < underlying → otm = underlying − strike

  steps = otm / strike_step
    steps <= -0.5          → ITM
    -0.5 < steps <=  0.5   → ATM
     0.5 < steps <=  1.5   → OTM1
     steps >  1.5          → OTM2+
"""
from __future__ import annotations

import numpy as np

BUCKETS = ["ITM", "ATM", "OTM1", "OTM2+"]


def infer_strike_step(strikes) -> float:
    """Smallest positive gap between consecutive distinct strikes."""
    s = np.array(sorted({float(x) for x in strikes}), dtype=float)
    if s.size < 2:
        return 1.0
    diffs = np.diff(s)
    diffs = diffs[diffs > 1e-9]
    return float(np.min(diffs)) if diffs.size else 1.0


def classify(underlying: float, strike: float, right: str, strike_step: float) -> str:
    """Return one of BUCKETS for a single contract at entry."""
    if not np.isfinite(underlying) or underlying <= 0 or strike_step <= 0:
        return "ATM"  # degenerate; caller may drop on low sample
    right = right.lower()
    if right in ("call", "c"):
        otm = strike - underlying
    else:  # put
        otm = underlying - strike
    steps = otm / strike_step
    if steps <= -0.5:
        return "ITM"
    if steps <= 0.5:
        return "ATM"
    if steps <= 1.5:
        return "OTM1"
    return "OTM2+"
