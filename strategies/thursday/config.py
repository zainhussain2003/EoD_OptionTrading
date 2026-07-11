from dataclasses import dataclass, field


@dataclass
class Config:
    # THURSDAY entry → FRIDAY expiry study, run on AAPL and TSLA only.
    tickers: list = field(default_factory=lambda: ['AAPL', 'TSLA'])
    # Both directions: buy a CALL (bet up) and a PUT (bet down) each week.
    option_types: list = field(default_factory=lambda: ['C', 'P'])
    risk_free_rate: float = 0.05
    backtest_days: int = 365
    entry_step_minutes: int = 5
    exit_step_minutes: int = 5
    min_hold_minutes: int = 5
    timezone: str = 'America/New_York'
    window_start_hour: int = 15
    window_end_hour: int = 16
    trades_csv: str = 'trades.csv'
