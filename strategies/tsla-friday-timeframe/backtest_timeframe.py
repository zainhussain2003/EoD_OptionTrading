#!/usr/bin/env python3
"""
TSLA FRIDAY — OPTIMAL ENTRY/EXIT TIME-FRAME ANALYSIS  (target-spend sized)

Finds the best *time frame* to ENTER and the best *time frame* to EXIT a TSLA
0DTE option over the whole regular session (9:30 AM–4:00 PM ET), on Fridays only,
for BOTH calls and puts.

A time frame is a contiguous window [start, end] of arbitrary length (5 minutes
up to the full day) and it need not snap to clean 5-minute marks — 12:32–12:45 is
a valid frame. Each frame's price is the MEAN of its 1-minute closes (so grouping
minutes into frames reduces noise instead of chasing individual ticks). A trade
enters during the entry frame at mean(entry) and exits during the exit frame at
mean(exit), with the exit frame starting at/after the entry frame ends.

Position sizing is identical to backtest_friday_sized.py:
    contracts = ceil(TARGET_SPEND / mean(entry_frame)), minimum 1
so TARGET_SPEND = 1.00 means a minimum of ~$100 premium per trade. Scoring ranks
frame pairs by win_rate × avg_payoff, and a second "outliers removed" pass drops
winning trades over OUTLIER_MAX and re-optimizes.

For each option type it saves to backtest_results/:
  *.csv   *.txt   *_outliers_removed.txt

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE LINES:                                                 ║
║    LOOKBACK_DAYS — calendar days to test                            ║
║    TARGET_SPEND  — minimum premium per share ($1.00 = ~$100/trade)  ║
║    OUTLIER_MAX   — winning trades over $ this are dropped in pass 2  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 730          # <───── window to test (calendar days)
TARGET_SPEND  = 1.00         # <───── minimum premium per share per trade
OUTLIER_MAX   = 2000         # <───── 2nd pass drops winning trades over $ this

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_timeframe.py
# ──────────────────────────────────────────────────────────────────────────
import math

from timeframe_engine import run_timeframe, CONTRACT_MULTIPLIER


def size_fn(entry_price):
    """Buy enough contracts to spend at least TARGET_SPEND/share (min 1)."""
    if entry_price <= 0:
        return 1
    return max(1, math.ceil(TARGET_SPEND / entry_price))


def score_key(s):
    """Rank by win_rate × avg_payoff (tiny win_rate tiebreaker when avg <= 0)."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def eligible(s):
    """Every frame pair with enough samples is eligible."""
    return True


if __name__ == "__main__":
    run_timeframe(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX EXPECTED PROFIT, target-spend sized (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        size_fn=size_fn,
        file_tag="tsla_friday_timeframe",
        outlier_max=OUTLIER_MAX,
        header_extra=(
            f"Position sizing: contracts = ceil(${TARGET_SPEND:.2f} / mean(entry_frame)), "
            f"min 1 — minimum ~${TARGET_SPEND * CONTRACT_MULTIPLIER:.0f} premium per "
            f"trade. Frames are arbitrary [start, end] windows; price = mean of the "
            f"1-min closes inside the frame."
        ),
    )
