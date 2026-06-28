"""
Configuration for the EoD option-trading strategy template.

ARCHITECT: this is one of the sections you modify when implementing a new idea.
Change the parameters here (tickers, target delta, DTE, window, etc.) to match
the strategy the user described. Keep it a plain dataclass so it stays easy to
diff and reason about.
"""
from dataclasses import dataclass, field


@dataclass
class Config:
    # --- Universe -----------------------------------------------------------
    tickers: list = field(default_factory=lambda: ["SPY"])

    # --- Strategy parameters (EDIT THESE for a new idea) --------------------
    # This template = sell a weekly out-of-the-money cash-secured put.
    target_delta: float = 0.05          # ~5-delta short put
    otm_pct_fallback: float = 0.05      # if delta solve unavailable, sell 5% OTM
    dte: int = 7                        # days to expiry of the put we sell
    contracts: int = 1                  # contracts per trade (100 mult applied)

    # Outlier threshold (dollars). The strategy emits a second "outliers removed"
    # set of artifacts/metrics that drops winning trades whose P&L exceeds this,
    # so a handful of fat-tail wins can't flatter the headline numbers.
    outlier_max: float = 2000.0

    # --- Backtest window ----------------------------------------------------
    lookback_days: int = 365            # calendar days of history to test
    timezone: str = "America/New_York"
    entry_hour: int = 15                # enter at 3:55pm ET (end of day)
    entry_minute: int = 55

    # --- Market assumptions -------------------------------------------------
    risk_free_rate: float = 0.05
    contract_multiplier: int = 100

    # --- Alpaca (paper) -----------------------------------------------------
    alpaca_paper: bool = True           # use paper/data endpoints, read-only
