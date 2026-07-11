"""
core/expiry.py — date-aware, EMPIRICAL-FIRST expiry & regime detection.

For each (symbol, trade_date) a same-day expiry exists **iff the dataset
contains a contract with `expiry == trade_date` for that symbol**. We use that,
not a hardcoded calendar. Each trade instance is tagged with a regime:

  same-day expiry present → `<DOW>-0DTE`            (e.g. "Fri-0DTE")
  no same-day expiry      → bridge to the next available expiry in the data,
                            labelled `<entryDOW>-><expiryDOW>` (e.g. "Mon->Fri"),
                            with days-to-expiry recorded so multi-day holds are
                            never mixed with true 0DTE.

The TUE_THU_ACTIVATION / ALWAYS_DAILY-style cadence constants in Config are kept
ONLY as a fallback when a date is absent from the data.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def dow(d: date) -> str:
    return _DOW[d.weekday()]


def build_expiry_index(df: pd.DataFrame, col_symbol: str, col_expiry: str,
                       col_ts: str) -> dict:
    """Map symbol → sorted list of expiry dates actually present in the data."""
    idx: dict = {}
    sub = df[[col_symbol, col_expiry]].drop_duplicates()
    for sym, grp in sub.groupby(col_symbol):
        idx[sym] = sorted({_as_date(x) for x in grp[col_expiry]})
    return idx


def available_expiries_for_date(expiries: list, trade_date: date) -> list:
    """Expiries on/after the trade date (same-day first, then forward)."""
    return [e for e in expiries if e >= trade_date]


def target_expiry(expiries_for_symbol: list, trade_date: date) -> Optional[date]:
    """The expiry a trade opened on `trade_date` should use:

    same-day if it exists, else the nearest FUTURE expiry present in the data.
    Returns None if the symbol has no expiry on/after the trade date.
    """
    forward = available_expiries_for_date(expiries_for_symbol, trade_date)
    return forward[0] if forward else None


def regime_label(trade_date: date, expiry: date) -> tuple:
    """Return (regime_str, days_to_expiry, is_0dte).

    0DTE   → "<DOW>-0DTE"            dte == 0
    bridge → "<entryDOW>-><expDOW>"  dte  > 0  (multi-day hold)
    """
    dte = (expiry - trade_date).days
    if dte == 0:
        return f"{dow(trade_date)}-0DTE", 0, True
    return f"{dow(trade_date)}->{dow(expiry)}", dte, False


def detect_cadence(expiry_index: dict) -> dict:
    """Per-symbol summary of the empirically observed expiry cadence, for
    run_config.json / the validation pass. Reports the set of expiry weekdays and
    the share of trade-eligible weekdays that carry a same-day expiry is computed
    elsewhere; here we just surface the distinct expiry DOWs seen."""
    out: dict = {}
    for sym, exps in expiry_index.items():
        dows = sorted({dow(e) for e in exps}, key=_DOW.index)
        out[sym] = {
            "n_expiries": len(exps),
            "expiry_dows": dows,
            "first_expiry": str(exps[0]) if exps else None,
            "last_expiry": str(exps[-1]) if exps else None,
        }
    return out


def _as_date(x) -> date:
    if isinstance(x, date) and not hasattr(x, "hour"):
        return x
    return pd.Timestamp(x).date()
