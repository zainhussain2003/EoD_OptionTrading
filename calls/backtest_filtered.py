#!/usr/bin/env python3
"""
BACKTEST  —  scoring method: PROFIT AMONG RELIABLE SETUPS

This first throws out any entry/exit time whose win rate is below MIN_WIN_RATE,
then — among the survivors — picks the one with the highest win_rate × avg_payoff.
It's the "best of both": it won't crown a 40%-win-rate lottery ticket, but among
the dependable setups it still maximizes profit.

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE TWO LINES:                                              ║
║    LOOKBACK_DAYS — calendar days to test (e.g. 100, 250, 500)         ║
║    MIN_WIN_RATE  — only consider pairs that win at least this often   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 365          # <───── window to test
MIN_WIN_RATE  = 0.55         # <───── reliability floor (0.55 = 55% win rate)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_filtered.py
# ──────────────────────────────────────────────────────────────────────────
from backtest_engine import run


def score_key(s):
    """Among eligible pairs, rank by win_rate × avg_payoff."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def eligible(s):
    """Only pairs that clear the win-rate floor may be chosen."""
    return s["wr"] >= MIN_WIN_RATE


if __name__ == "__main__":
    run(
        lookback_days=LOOKBACK_DAYS,
        method_label="PROFIT AMONG RELIABLE SETUPS (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        file_tag=f"filtered{int(MIN_WIN_RATE * 100)}",
        header_extra=f"Reliability floor: only pairs with win_rate >= "
                     f"{MIN_WIN_RATE:.0%} are considered",
    )
