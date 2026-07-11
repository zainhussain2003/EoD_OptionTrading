#!/usr/bin/env python3
"""
FRIDAY INTRADAY, CONCENTRATION-CAPPED — OPTIMAL ENTRY/EXIT TIME-FRAME ANALYSIS

Finds the best *time frame* to ENTER and the best *time frame* to EXIT a 0DTE
Friday-expiry option over the whole regular session (9:30 AM–4:00 PM ET), on
Fridays only, for BOTH calls and puts, across a basket of large-cap names:
TSLA, AMZN, AAPL, NVDA, GOOGL, MSFT, ORCL.

A time frame is a contiguous window [start, end] of arbitrary length (5 minutes
up to the full day) and it need not snap to clean 5-minute marks — 12:32–12:45 is
a valid frame. Each frame's price is the MEAN of its 1-minute closes (so grouping
minutes into frames reduces noise instead of chasing individual ticks). A trade
enters during the entry frame at mean(entry) and exits during the exit frame at
mean(exit), with the exit frame starting at/after the entry frame ends.

Position sizing:
    contracts = ceil(TARGET_SPEND / mean(entry_frame)), minimum 1
so TARGET_SPEND = 1.00 means a minimum of ~$100 premium per trade. Scoring ranks
frame pairs by win_rate × avg_payoff.

THE CONCENTRATION CAP (replaces the old $-outlier system)
---------------------------------------------------------
There is no OUTLIER_MAX and no winning-trade dollar-drop pass. Pass 1 is
unconstrained. Pass 2 re-optimizes but only among frames that survive a
single-transaction concentration cap:

    single_trade_share = (largest single winning trade P&L) / (net total P&L)
    eligible  ⇔  net_total_pnl > 0  AND  single_trade_share <= MAX_SINGLE_TRADE_SHARE

No trade is ever removed — the cap only decides which frame may be chosen. The
point is to see whether an edge is broad-based or just one jackpot print: a fat
$2,000 day inside a $10,000 total is only 20% (fine — big swings are normal for
options), but if one trade is >51% of the total the window is luck-driven and
unlikely to repeat, so it is disqualified in pass 2.

For each option type it saves to backtest_results/:
  *.csv   *.txt   *_concentration_capped.txt

╔══════════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE LINES:                                                      ║
║    LOOKBACK_DAYS           — calendar days to test                       ║
║    TARGET_SPEND            — minimum premium per share ($1.00 = ~$100)    ║
║    MAX_SINGLE_TRADE_SHARE  — biggest single win as a share of total P&L   ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS           = 730     # <───── window to test (calendar days)
TARGET_SPEND            = 1.00    # <───── minimum premium per share per trade
MAX_SINGLE_TRADE_SHARE  = 0.51    # <───── pass 2: biggest single win <= this × total P&L

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
    """Pass 1: every frame pair with enough samples is eligible (no cap)."""
    return True


def eligible_capped(s):
    """Pass 2: eligible only if the frame's net total P&L is positive AND its
    biggest single winning trade is at most MAX_SINGLE_TRADE_SHARE of that total.
    A frame carried by one jackpot trade (share > cap) is disqualified."""
    share = s.get("single_trade_share")
    return s["total"] > 0 and share is not None and share <= MAX_SINGLE_TRADE_SHARE


if __name__ == "__main__":
    run_timeframe(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX EXPECTED PROFIT, target-spend sized (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        size_fn=size_fn,
        file_tag="friday_intraday_concentration_capped",
        eligible_capped=eligible_capped,
        cap_share=MAX_SINGLE_TRADE_SHARE,
        header_extra=(
            f"Position sizing: contracts = ceil(${TARGET_SPEND:.2f} / mean(entry_frame)), "
            f"min 1 — minimum ~${TARGET_SPEND * CONTRACT_MULTIPLIER:.0f} premium per "
            f"trade. Pass 2 concentration cap: biggest single win <= "
            f"{MAX_SINGLE_TRADE_SHARE:.0%} of net total P&L."
        ),
    )
