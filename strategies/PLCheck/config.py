from dataclasses import dataclass, field


@dataclass
class Config:
    """P/L check: buy the ATM TSLA CALL at 3:45 PM ET, sell it at 3:55 PM ET.

    This is a fixed-window study (no frame search) over the last `backtest_days`
    calendar days. TSLA trades 0DTE options on Fridays, so those are the days the
    data-capture layer produces real option bars — this study evaluates one trade
    per such day.
    """
    # TSLA CALLS only for this study.
    tickers: list = field(default_factory=lambda: ['TSLA'])
    option_types: list = field(default_factory=lambda: ['C'])

    risk_free_rate: float = 0.05
    backtest_days: int = 730          # look back this many calendar days
    timezone: str = 'America/New_York'

    # Fixed entry/exit clock, in MINUTES of the day (ET). 945 = 3:45 PM, 955 = 3:55 PM.
    entry_minute: int = 945           # 3:45 PM ET — buy the call
    exit_minute: int = 955            # 3:55 PM ET — sell the call
    # If the exact entry/exit minute has no bar, use the nearest available minute
    # within this many minutes; otherwise the day is skipped (no usable price).
    price_tolerance_minutes: int = 3

    # Position sizing: contracts = MAX(1, CEILING(budget / (entry_price * 100))).
    # With a $100 budget this keeps each trade's premium spend near $100.
    per_trade_budget: float = 100.0

    # Full regular-session window, in MINUTES of the day (ET). The ATM strike is
    # picked from the price at the session open (570 = 9:30 AM, 960 = 4:00 PM),
    # matching the rest of the repo — the entry/exit clock above sits inside it.
    window_start_minute: int = 570    # 9:30 AM ET (market open)
    window_end_minute: int = 960      # 4:00 PM ET (market close)

    trades_csv: str = 'trades.csv'
