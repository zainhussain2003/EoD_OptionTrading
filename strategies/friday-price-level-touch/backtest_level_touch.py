#!/usr/bin/env python3
"""
FRIDAY PRICE-LEVEL-TOUCH ANALYSIS

For a basket of tickers, each with its own dollar move threshold, this study asks:
starting from Thursday's near-close price, how often does Friday TOUCH that price
plus/minus the threshold, at any point between 9:30 AM and 4:00 PM ET?

  TSLA ±$8    AAPL ±$6    NVDA ±$5    MSFT ±$10    ORCL ±$7

Thursday's baseline is captured minute-by-minute at 3:50, 3:51, 3:52, 3:53, 3:54
and 3:55 PM (plus a 3:50–55 average), so we can compare which near-close minute is
the steadiest baseline. For each Friday we record whether the session high reached
`ref + threshold` and whether the session low reached `ref - threshold`, plus the
full max-up / max-down swing from each baseline.

This is a stock price-level study — there are no options and no P&L. TARGET_SPEND
and OUTLIER_MAX below are option-template parameters with no effect here; they are
carried only to document the requested run.

For each ticker it saves to backtest_results/:
  level_touch_<ticker>_<lookback>days_<stamp>.txt
and across all tickers:
  touch_summary_<lookback>days_<stamp>.csv
  swings_<lookback>days_<stamp>.csv

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THIS LINE:                                                   ║
║    LOOKBACK_DAYS — calendar days to test                            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 730          # <───── window to test (calendar days)
TARGET_SPEND  = 1.00         # <───── inert here (no premium to spend)
OUTLIER_MAX   = 2000         # <───── inert here (no trade P&L to cap)

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_level_touch.py
# ──────────────────────────────────────────────────────────────────────────
from level_touch_engine import run_level_touch


if __name__ == "__main__":
    run_level_touch(
        lookback_days=LOOKBACK_DAYS,
        header_extra=(
            f"Touch = Friday session high/low reaches Thursday ref ± per-ticker "
            f"threshold. Swings measured from each Thursday baseline. "
            f"(TARGET_SPEND ${TARGET_SPEND:.2f} / OUTLIER_MAX ${OUTLIER_MAX:.0f} "
            f"carried as inert metadata.)"
        ),
    )
