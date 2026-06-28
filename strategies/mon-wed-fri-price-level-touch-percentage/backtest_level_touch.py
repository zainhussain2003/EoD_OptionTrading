#!/usr/bin/env python3
"""
MON/WED/FRI PRICE-LEVEL-TOUCH ANALYSIS (PERCENTAGE)

For a basket of tickers, each evaluated at several PERCENTAGE move thresholds and
on three scan days, this study asks: starting from the prior trading day's
near-close price R, how often does the scan day (Monday, Wednesday or Friday) TOUCH
R × (1 ± pct), at any point between 9:30 AM and 4:00 PM ET?

  Every ticker is tested at ±1%, ±1.5%, ±2%, ±2.5% and ±3% (edit config.py).
  Each scan day uses the prior trading day's close: Mon←Fri, Wed←Tue, Fri←Thu.

The baseline is captured minute-by-minute at 3:50, 3:51, 3:52, 3:53, 3:54 and 3:55
PM (plus a 3:50–55 average), so we can compare which near-close minute is the
steadiest. For each scan day we record whether the session high reached
`R × (1 + pct)` and whether the session low reached `R × (1 - pct)`, plus the full
max-up / max-down swing from each baseline (the biggest single-day move each way,
shown as a % of R with the dollar move in brackets). Results are printed day after
day per ticker, then summarized in a combined day-comparison table.

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
            f"Touch = scan-day session high/low reaches prior-day ref × (1 ± pct) at "
            f"each per-ticker percentage (1% / 1.5% / 2% / 2.5% / 3%), for Mon/Wed/Fri. "
            f"Swings shown as % of reference with the dollar move in brackets. "
            f"(TARGET_SPEND ${TARGET_SPEND:.2f} / OUTLIER_MAX ${OUTLIER_MAX:.0f} "
            f"carried as inert metadata.)"
        ),
    )
