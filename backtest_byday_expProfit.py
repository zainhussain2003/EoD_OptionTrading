#!/usr/bin/env python3
"""
BACKTEST BY DAY  —  scoring method: MAX EXPECTED PROFIT  (win_rate × avg_payoff)

Finds the optimal entry/exit time separately for Monday, Wednesday, and Friday.
At the bottom shows a combo table so you can compare trading all 3 days vs only
the best day(s).

Saves two files to backtest_results/:
  *.csv  — structured data: per-day rows, summary, combo comparison table
  *.txt  — full heatmap output in plain text (open in any text editor or IDE)

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THIS ONE LINE to test any window (e.g. 100, 250, 500 days): ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 138          # <───── EDIT ONLY THIS LINE (calendar days to test)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_byday_expProfit.py
# ──────────────────────────────────────────────────────────────────────────
from backtest_engine import run_byday


def score_key(s):
    """Rank by win_rate × avg_payoff (tiny win_rate tiebreaker when avg <= 0)."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def eligible(s):
    """Every pair with enough samples is eligible."""
    return True


if __name__ == "__main__":
    run_byday(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX EXPECTED PROFIT (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        file_tag="byday_expProfit",
    )
