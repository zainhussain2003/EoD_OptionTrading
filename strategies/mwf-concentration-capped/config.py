from dataclasses import dataclass, field


@dataclass
class DaySpec:
    """One weekday's scan parameters. Each MWF day gets its own lookback and
    trading window, exactly like the by-day sized backtests:

      - Monday & Wednesday : 140 calendar days, 3:00-4:00 PM ET window
      - Friday             : 730 calendar days, 2:00-4:00 PM ET window (with a
                             Thursday fallback for weeks the Friday session is
                             closed — the weekly option rolls to Thursday)

    Windows are stored in minutes-of-day ET: 840 = 2:00 PM, 900 = 3:00 PM,
    960 = 4:00 PM.
    """
    name: str
    weekday: int              # Monday=0, Wednesday=2, Friday=4
    lookback_days: int
    window_start_minute: int
    window_end_minute: int
    thursday_fallback: bool = False


@dataclass
class Config:
    # TSLA and AAPL only, BOTH calls and puts, over Monday / Wednesday / Friday.
    tickers: list = field(default_factory=lambda: ['TSLA', 'AAPL'])
    option_types: list = field(default_factory=lambda: ['C', 'P'])

    risk_free_rate: float = 0.05
    timezone: str = 'America/New_York'
    trades_csv: str = 'trades.csv'

    # Per-day scan specs. Monday & Wednesday share the short lookback / 3-4 PM
    # window; Friday keeps the long lookback / 2-4 PM window + Thursday fallback.
    days: list = field(default_factory=lambda: [
        DaySpec('Monday',    0, 140, 900, 960, thursday_fallback=False),
        DaySpec('Wednesday', 2, 140, 900, 960, thursday_fallback=False),
        DaySpec('Friday',    4, 730, 840, 960, thursday_fallback=True),
    ])
