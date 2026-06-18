from dataclasses import dataclass, field


@dataclass
class Config:
    # tickers: list = field(default_factory=lambda: ['AAPL', 'NVDA', 'TSLA', 'MSFT'])
    tickers: list = field(default_factory=lambda: ['AAPL', 'TSLA'])
    risk_free_rate: float = 0.05
    backtest_days: int = 60
    entry_step_minutes: int = 5
    exit_step_minutes: int = 5
    min_hold_minutes: int = 5
    timezone: str = 'America/New_York'
    window_start_hour: int = 15
    window_end_hour: int = 16
    trades_csv: str = 'trades.csv'
