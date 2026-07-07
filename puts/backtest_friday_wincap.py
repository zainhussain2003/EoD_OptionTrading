#!/usr/bin/env python3
"""
BACKTEST FRIDAY ONLY  —  TARGET-SPEND SIZING  +  WIN-RATE CAP

Same engine as backtest_friday_sized.py (Friday 0DTE, max-expected-profit
scoring with target-spend position sizing) with ONE change to how the "best"
schedule is chosen:

    *Instead of the old OUTLIER_MAX system* (which dropped winning trades over a
    dollar threshold), this version constrains the SELECTED schedule by WIN RATE.
    Only (entry, exit) pairs whose win rate lands inside a target band are
    eligible, so the chosen "best day" is a realistic 45-50% (±1%) rather than an
    overfit, sky-high win rate.

    eligible  ⇔  (MAX_WIN_RATE_LOW - WIN_RATE_TOL) <= win_rate <= (MAX_WIN_RATE_HIGH + WIN_RATE_TOL)

With the defaults below the eligible band is [0.44, 0.51], i.e. 45-50% ±1%.

Position sizing is unchanged: contracts = ceil(TARGET_SPEND / option_price),
minimum 1. TARGET_SPEND is the per-share premium floor ($1.00 ≈ $100/trade).

Saves two files to backtest_results/ (with contracts + cost columns):
  *.csv   *.txt

╔══════════════════════════════════════════════════════════════════════╗
║  CHANGE THESE LINES:                                                 ║
║    LOOKBACK_DAYS      — calendar days to test                       ║
║    TARGET_SPEND       — minimum premium per share ($1.00 = ~$100)   ║
║    MAX_WIN_RATE_LOW   — lower edge of the target win-rate band      ║
║    MAX_WIN_RATE_HIGH  — upper edge (the "up to 50%" cap)            ║
║    WIN_RATE_TOL       — ± tolerance around the band                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""

LOOKBACK_DAYS = 730          # <───── window to test (calendar days)
WINDOW_START_HOUR = 14       # <───── trading window START hour, 24h ET (15=3PM, 14=2PM)
WINDOW_END_HOUR   = 16       # <───── trading window END   hour, 24h ET (16=4PM, 15=3PM)
TARGET_SPEND  = 1.00         # <───── minimum premium per share per trade

# ── WIN-RATE CAP (replaces the old OUTLIER_MAX system) ──────────────────────
# The selected "best day" must have a win rate inside the band below, so it
# lands at a realistic 45-50% instead of an overfit high win rate.
MAX_WIN_RATE_LOW  = 0.45     # <───── lower edge of the target win-rate band
MAX_WIN_RATE_HIGH = 0.50     # <───── upper edge of the band (the "up to 50%" cap)
WIN_RATE_TOL      = 0.01     # <───── ± tolerance → eligible band [0.44, 0.51]

# ──────────────────────────────────────────────────────────────────────────
# Engine below. Run with:   python backtest_friday_wincap.py
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
    """Only pairs whose win rate lands in the target band are eligible, so the
    chosen 'best day' is a realistic 45-50% (±1%) rather than overfit."""
    lo = MAX_WIN_RATE_LOW - WIN_RATE_TOL
    hi = MAX_WIN_RATE_HIGH + WIN_RATE_TOL
    return lo <= s["wr"] <= hi


if __name__ == "__main__":
    run_byday(
        lookback_days=LOOKBACK_DAYS,
        method_label="MAX EXPECTED PROFIT, target-spend sized, win-rate capped (win_rate × avg_payoff)",
        score_key=score_key,
        eligible=eligible,
        file_tag="friday_wincap",
        days=[("Friday", 4)],
        combos=[("Friday only", ["Friday"])],
        size_fn=size_fn,
        friday_thursday_fallback=True,
        window_start_hour=WINDOW_START_HOUR,
        window_end_hour=WINDOW_END_HOUR,
        header_extra=(
            f"Position sizing: contracts = ceil(${TARGET_SPEND:.2f} / option_price), "
            f"min 1 — minimum ~${TARGET_SPEND * CONTRACT_MULTIPLIER:.0f} premium per "
            f"trade (more if the option costs over ${TARGET_SPEND:.2f}/share). "
            f"Win-rate cap: only schedules with win rate in "
            f"[{MAX_WIN_RATE_LOW - WIN_RATE_TOL:.0%}, {MAX_WIN_RATE_HIGH + WIN_RATE_TOL:.0%}] "
            f"are eligible, so the best day lands at {MAX_WIN_RATE_LOW:.0%}-{MAX_WIN_RATE_HIGH:.0%}."
        ),
    )
