#!/usr/bin/env python3
"""
BACKTEST  —  scoring method: MAX EXPECTED PROFIT   (win_rate × avg_payoff)

This picks the entry/exit time with the highest probability-weighted profit.
It rewards big average payoffs even if the win rate is below 50% — i.e. it
will happily choose a setup that loses most days but wins big occasionally.

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THIS ONE LINE to test any window (e.g. 100, 250, 500 days):   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 365          # <───── EDIT ONLY THIS LINE (calendar days to test)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python custom_backtest.py
# ──────────────────────────────────────────────────────────────────────────
from backtest_engine import run


def score_key(s):
    """Rank by win_rate × avg_payoff (tiny win_rate tiebreaker when avg <= 0)."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def eligible(s):
    """Every pair with enough samples is eligible."""
    return True


if __name__ == "__main__":
    run(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX EXPECTED PROFIT (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        file_tag="expProfit",
    )
