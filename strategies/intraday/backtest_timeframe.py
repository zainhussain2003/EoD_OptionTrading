#!/usr/bin/env python3
"""
ALL-DAYS INTRADAY — OPTIMAL ENTRY/EXIT TIME-FRAME ANALYSIS  (target-spend sized)

Finds the best *time frame* to ENTER and the best *time frame* to EXIT an option
over the whole regular session (9:30 AM–4:00 PM ET), same-session intraday, for
BOTH calls and puts — for every weekday, each with its own expiry / lookback /
ticker set (see config.DAY_SPECS):

    Monday     entry Monday     → Monday expiry      (0DTE)  150 d  Mag7−META
    Tuesday    entry Tuesday    → Wednesday expiry   (1DTE)  150 d  Mag7−META
    Wednesday  entry Wednesday  → Wednesday expiry   (0DTE)  150 d  Mag7−META
    Thursday   entry Thursday   → Friday expiry      (1DTE)  730 d  Mag7−META+AMD+ORCL
    Friday     entry Friday     → Friday expiry      (0DTE)  730 d  Mag7−META+AMD+ORCL

A time frame is a contiguous window [start, end] of arbitrary length (5 minutes
up to the full day), not snapped to clean 5-minute marks. Each frame's price is
the MEAN of its 1-minute closes. A trade enters during the entry frame at
mean(entry) and exits during the exit frame at mean(exit), exit_start >= entry_end.

Position sizing: contracts = ceil(TARGET_SPEND / mean(entry_frame)), min 1
(TARGET_SPEND = 1.00 ⇒ ≥ ~$100 premium/trade). Frame pairs ranked by
win_rate × avg_payoff.

The pipeline entry point is strategy.py (it drives all five days and emits the
day-keyed metrics.json). Running this file directly produces the full terminal
report + per-day/per-ticker CSV/TXT for every day.

╔══════════════════════════════════════════════════════════════════════╗
║  Knobs:  TARGET_SPEND (here).  Per-day expiry/lookback/tickers live   ║
║          in config.DAY_SPECS.                                         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

TARGET_SPEND = 1.00          # <───── minimum premium per share per trade

# ──────────────────────────────────────────────────────────────────────────
import math

from timeframe_engine import run_timeframe, CONTRACT_MULTIPLIER
from config import Config, DAY_SPECS

DAYNAME = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


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
    for spec in DAY_SPECS:
        cfg = Config(tickers=list(spec["tickers"]), entry_weekday=spec["weekday"],
                     expiry_weekday=spec["expiry_weekday"],
                     backtest_days=spec["lookback"])
        run_timeframe(
            lookback_days=spec["lookback"],
            method_label=f"{spec['name']} intraday — MAX EXPECTED PROFIT "
                         f"(win_rate × avg_payoff)",
            score_key=score_key,
            eligible=eligible,
            size_fn=size_fn,
            file_tag=f"intraday_{spec['name'].lower()}",
            outlier_max=None,
            header_extra=(
                f"{spec['name']} entry → {DAYNAME[spec['expiry_weekday']]} expiry, "
                f"lookback {spec['lookback']}d. Sizing: ceil(${TARGET_SPEND:.2f} / "
                f"mean(entry)), min 1 (~${TARGET_SPEND * CONTRACT_MULTIPLIER:.0f}/trade)."
            ),
            config=cfg,
        )
