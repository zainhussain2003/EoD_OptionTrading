from dataclasses import dataclass, field


@dataclass
class Config:
    """Mon/Wed/Fri win-rate-capped 0DTE study — TSLA & AAPL, calls AND puts.

    The backtester captures the WIDEST window used by any weekday (2:00-4:00 PM
    ET) over the LONGEST lookback (Friday's 730 days); the by-day engine then
    slices each weekday to its own lookback and trading window at analysis time.
    """
    tickers: list = field(default_factory=lambda: ['TSLA', 'AAPL'])
    risk_free_rate: float = 0.05
    # Longest per-day lookback (Friday). Mon/Wed are trimmed to their own,
    # shorter lookback inside the engine.
    backtest_days: int = 730
    entry_step_minutes: int = 5
    exit_step_minutes: int = 5
    min_hold_minutes: int = 5
    timezone: str = 'America/New_York'
    # Capture window, in MINUTES of the day (ET). 840 = 2:00 PM, 960 = 4:00 PM.
    # This is the union of every weekday's window; narrower per-day windows are
    # applied when the engine scores each day.
    window_start_minute: int = 840    # 2:00 PM ET
    window_end_minute: int = 960      # 4:00 PM ET
    # Both option types are analyzed in one run.
    option_types: list = field(default_factory=lambda: ['C', 'P'])
    trades_csv: str = 'trades.csv'
