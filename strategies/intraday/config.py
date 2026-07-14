from dataclasses import dataclass, field

# ── ticker universes ────────────────────────────────────────────────────────
# "Mag 7 minus META" for every day.
MAG6 = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA']
# Thursday & Friday additionally include AMD and Oracle.
MAG6_PLUS = MAG6 + ['AMD', 'ORCL']

# ── per-weekday intraday specs ──────────────────────────────────────────────
# Each day is its own same-session (buy & sell that day) intraday study, trading
# the given expiry weekday (Mon=0 … Fri=4). expiry == entry weekday ⇒ 0DTE.
#   name         entry  expiry  DTE  lookback  tickers
DAY_SPECS = [
    {'name': 'Monday',    'weekday': 0, 'expiry_weekday': 0, 'lookback': 150, 'tickers': MAG6},
    {'name': 'Tuesday',   'weekday': 1, 'expiry_weekday': 2, 'lookback': 150, 'tickers': MAG6},
    {'name': 'Wednesday', 'weekday': 2, 'expiry_weekday': 2, 'lookback': 150, 'tickers': MAG6},
    {'name': 'Thursday',  'weekday': 3, 'expiry_weekday': 4, 'lookback': 730, 'tickers': MAG6_PLUS},
    {'name': 'Friday',    'weekday': 4, 'expiry_weekday': 4, 'lookback': 730, 'tickers': MAG6_PLUS},
]


@dataclass
class Config:
    """One day's intraday configuration. The driver (strategy.py) builds a Config
    per entry in DAY_SPECS, so `tickers`, `backtest_days`, `entry_weekday`, and
    `expiry_weekday` are set per day; the rest are shared defaults."""
    tickers: list = field(default_factory=lambda: list(MAG6))
    entry_weekday: int = 4          # Mon=0 … Fri=4 (set per day)
    expiry_weekday: int = 4         # expiry day-of-week; == entry_weekday ⇒ 0DTE
    risk_free_rate: float = 0.05
    backtest_days: int = 730
    entry_step_minutes: int = 5
    exit_step_minutes: int = 5
    min_hold_minutes: int = 5
    timezone: str = 'America/New_York'
    # Full regular-session window, in MINUTES of the day (ET). 570 = 9:30 AM,
    # 960 = 4:00 PM.
    window_start_minute: int = 570    # 9:30 AM ET (market open)
    window_end_minute: int = 960      # 4:00 PM ET (market close)
    option_types: list = field(default_factory=lambda: ['C', 'P'])
    trades_csv: str = 'trades.csv'
