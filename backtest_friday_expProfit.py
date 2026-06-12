#!/usr/bin/env python3
"""
BACKTEST FRIDAY ONLY  —  scoring method: MAX EXPECTED PROFIT  (win_rate × avg_payoff)

Same as backtest_byday_expProfit.py, but looks at FRIDAY expiries only (0DTE —
the option expires the same day). Finds each equity's optimal Friday entry/exit
time, shows per-day P&L, all heatmaps, and a per-equity + combined summary.

Saves two files to backtest_results/:
  *.csv  — structured data: per-day rows, summary, per-equity P&L
  *.txt  — full heatmap output in plain text (open in any text editor or IDE)

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THIS ONE LINE to test any window (e.g. 100, 250, 500 days): ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 365          # <───── EDIT ONLY THIS LINE (calendar days to test)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_friday_expProfit.py
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
        file_tag="friday_expProfit",
        days=[("Friday", 4)],
        combos=[("Friday only", ["Friday"])],
    )
