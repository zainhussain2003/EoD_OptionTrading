#!/usr/bin/env python3
"""
WEEKLY MOVE PROBABILITY

For a basket of tickers (TSLA, AAPL, NVDA, ORCL, MSFT), using stock prices only,
this study measures the probability that one week later — at the following
Friday's close — the price has:

  • moved UP   ≥ +threshold   (default +1.5%),
  • moved DOWN ≤ -threshold   (default -1.5%), or
  • stayed FLAT within the ±threshold band (the remainder).

The three probabilities sum to 100% by construction (terminal, close-to-close).

Reference price (both legs): the AVERAGE of the 1-minute CLOSE prices over the
3:50–4:00 PM ET window (the ten bars 3:50 … 3:59). If a Friday is a market
holiday / closed, the leg steps back to the prior Thursday's 3:50–4:00 window.

Entry = each Friday's reference; exit = the following Friday's reference.
Weekly return = (exit_ref / entry_ref) - 1.

For each ticker it saves to backtest_results/:
  weekly_move_<ticker>_<lookback>days_<stamp>.txt
and across all tickers:
  probability_summary_<lookback>days_<stamp>.csv
  weekly_log_<lookback>days_<stamp>.csv

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE LINES:                                                 ║
║    LOOKBACK_DAYS — calendar days of Fridays to test                 ║
║    THRESHOLD     — the ±band defining up / down / flat              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 730          # <───── window to test (calendar days, ~2 years)
THRESHOLD     = 0.015        # <───── ±band: up >= +1.5%, down <= -1.5%, else flat

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_weekly_move.py
# ──────────────────────────────────────────────────────────────────────────
from weekly_move_engine import run_weekly_move


if __name__ == "__main__":
    run_weekly_move(
        lookback_days=LOOKBACK_DAYS,
        threshold=THRESHOLD,
        header_extra=(
            f"Bucket: up if weekly return >= +{THRESHOLD:.2%}, "
            f"down if <= -{THRESHOLD:.2%}, else flat. "
            f"Reference = average of 3:50-4:00 PM ET minute closes "
            f"(Thursday fallback on Friday holidays)."
        ),
    )
