from dataclasses import dataclass, field


@dataclass
class Config:
    # TSLA only for this study (Friday optimal entry/exit time-frame analysis).
    tickers: list = field(default_factory=lambda: ['TSLA'])
    risk_free_rate: float = 0.05
    backtest_days: int = 730
    entry_step_minutes: int = 5
    exit_step_minutes: int = 5
    min_hold_minutes: int = 5
    timezone: str = 'America/New_York'
    # Full regular-session window, in MINUTES of the day (ET). 9:30 AM is not an
    # integer hour, so this study works in minutes rather than the hour knobs the
    # narrow-window backtests use. 570 = 9:30 AM, 960 = 4:00 PM.
    window_start_minute: int = 570    # 9:30 AM ET (market open)
    window_end_minute: int = 960      # 4:00 PM ET (market close)
    # Both option types are analyzed in one run.
    option_types: list = field(default_factory=lambda: ['C', 'P'])
    trades_csv: str = 'trades.csv'
