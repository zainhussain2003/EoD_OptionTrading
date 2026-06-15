#!/usr/bin/env python3
"""
BACKTEST FRIDAY ONLY  —  TARGET-SPEND POSITION SIZING

Identical to backtest_friday_expProfit.py (Friday 0DTE, max-expected-profit
scoring) with ONE change: instead of always buying exactly 1 contract, it buys
enough contracts to spend a minimum target amount per trade.

    contracts = ceil(TARGET_SPEND / option_price), minimum 1

So with TARGET_SPEND = 1.00:
    price $0.10  -> 10 contracts   (spend $1.00/share  = $100 actual)
    price $0.55  ->  2 contracts   (spend $1.10/share  = $110 actual)
    price $1.00  ->  1 contract    (spend $1.00/share  = $100 actual)
    price $1.50  ->  1 contract    (spend $1.50/share  = $150 actual)

NOTE on units: option prices are quoted per share, and 1 contract = 100 shares.
TARGET_SPEND is the per-share premium floor, so TARGET_SPEND = 1.00 means a
minimum of ~$100 of real premium per trade (more if the option costs > $1.00).

Because P&L is now scaled by the contract count, this also changes which
entry/exit time is "optimal": cheap-option windows (late afternoon, near
expiry) get more weight since you buy more contracts there. Win RATE is
unchanged — buying more contracts doesn't change whether a trade wins, only
how big the win/loss is. Watch the "return on spend" line: that, not raw P&L,
is the fair way to compare this against the 1-contract version.

Saves two files to backtest_results/ (with contracts + cost columns):
  *.csv   *.txt

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE TWO LINES:                                             ║
║    LOOKBACK_DAYS — calendar days to test                            ║
║    TARGET_SPEND  — minimum premium per share ($1.00 = ~$100/trade)  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 730          # <───── window to test (calendar days)
TARGET_SPEND  = 1.00         # <───── minimum premium per share per trade
OUTLIER_MAX   = 2000         # <───── 2nd pass drops winning trades over $ this

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_friday_sized.py
# ──────────────────────────────────────────────────────────────────────────
import math

from backtest_engine import run_byday, CONTRACT_MULTIPLIER


def size_fn(entry_price):
    """Buy enough contracts to spend at least TARGET_SPEND/share (min 1)."""
    if entry_price <= 0:
        return 1
    return max(1, math.ceil(TARGET_SPEND / entry_price))


def score_key(s):
    """Rank by win_rate × avg_payoff (tiny win_rate tiebreaker when avg <= 0)."""
    return s["wr"] * max(s["avg"], 0.0) + s["wr"] * 0.001


def eligible(s):
    """Every pair with enough samples is eligible."""
    return True


if __name__ == "__main__":
    run_byday(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX EXPECTED PROFIT, target-spend sized (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        file_tag="friday_sized",
        days=[("Friday", 4)],
        combos=[("Friday only", ["Friday"])],
        size_fn=size_fn,
        outlier_max=OUTLIER_MAX,
        friday_thursday_fallback=True,
        header_extra=(
            f"Position sizing: contracts = ceil(${TARGET_SPEND:.2f} / option_price), "
            f"min 1 — minimum ~${TARGET_SPEND * CONTRACT_MULTIPLIER:.0f} premium per "
            f"trade (more if the option costs over ${TARGET_SPEND:.2f}/share). "
            f"P&L and the optimal time reflect the contract count."
        ),
    )
