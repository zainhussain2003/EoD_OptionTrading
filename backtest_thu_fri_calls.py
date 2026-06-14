#!/usr/bin/env python3
"""
BACKTEST — THURSDAY entry → FRIDAY-expiry CALL, touch-probability of returns.

You buy the ATM Friday-expiry call on THURSDAY between 3:55 and 3:59 PM ET
(one row per minute), then watch it all day FRIDAY. This reports, for each
entry minute, the historical probability that the option's Friday session HIGH
reached each return target — i.e. "if I pay $X on Thursday, how often does it
hit 2×, 2.5× … at some point on Friday?"

RETURN multiples are profit ÷ premium:  target_price = entry × (1 + multiple)
    1.0x  → ×2.00  (a $0.50 option has to reach $1.00 — double your money)
    1.5x  → ×2.50  ($0.50 → $1.25)
    2.0x  → ×3.00  ($0.50 → $1.50)
    2.5x  → ×3.50  ($0.50 → $1.75)

Saves a timestamped .csv (detail + summary) and .txt (full tables) to
thu_fri_results/.

╔══════════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE TWO LINES:                                                  ║
║    LOOKBACK_DAYS    — calendar days of history to test                    ║
║    RETURN_MULTIPLES — the profit targets, as multiples of premium paid    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 365                       # <───── window to test (calendar days)
RETURN_MULTIPLES = [1.0, 1.5, 2.0, 2.5]   # <───── profit targets (×premium paid)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_thu_fri_calls.py
# ──────────────────────────────────────────────────────────────────────────
from thu_fri_engine import run


if __name__ == "__main__":
    run(lookback_days=LOOKBACK_DAYS, multiples=RETURN_MULTIPLES)
