#!/usr/bin/env python3
"""
BACKTEST  —  scoring method: MAX RELIABILITY   (win_rate only)

This picks the entry/exit time that wins the highest PERCENTAGE of the time,
regardless of how big the wins are. Average payoff is used only to break ties
between pairs with identical win rates. Use this to find the steadiest setup.

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THIS ONE LINE to test any window (e.g. 100, 250, 500 days):   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 365          # <───── EDIT ONLY THIS LINE (calendar days to test)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_winrate.py
# ──────────────────────────────────────────────────────────────────────────
from backtest_engine import run


def score_key(s):
    """Rank by win_rate first; avg_payoff only breaks ties."""
    return (s["wr"], s["avg"])


def eligible(s):
    """Every pair with enough samples is eligible."""
    return True


if __name__ == "__main__":
    run(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX RELIABILITY (win_rate only)",
        score_key=score_key,
        eligible=eligible,
        file_tag="winRate",
    )
