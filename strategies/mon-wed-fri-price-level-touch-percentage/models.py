from dataclasses import dataclass, field
from datetime import date


@dataclass
class OptionContract:
    ticker: str
    contract_symbol: str
    strike: float
    expiry: date
    bid: float
    ask: float
    mid_price: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float = 0.0
    theta_hourly: float = 0.0
    in_the_money: bool = False


@dataclass
class BacktestPairResult:
    entry_minute: int
    exit_minute: int
    win_rate: float
    avg_payoff: float
    score: float
    n_trades: int


# How each (date, strike) data pull was sourced.
SOURCE_REAL = 'REAL Alpaca option bars'
SOURCE_SIM = 'Black-Scholes simulation'
SOURCE_NO_STOCK = 'skipped — no stock bars'


@dataclass
class LevelTouchRecord:
    """One scan-day's touch/swing outcome measured against a single baseline
    reference price (the prior trading day's 3:52 PM close, etc.) at one
    percentage threshold."""
    date: str                 # the scan-day date (a Monday/Wednesday/Friday)
    ticker: str
    day: str                  # 'Monday' | 'Wednesday' | 'Friday'
    ref_label: str            # baseline minute: '3:52 PM' or '3:50–55 avg'
    ref_price: float          # baseline price R (prior trading day's close)
    pct: float                # fractional move threshold, e.g. 0.025 for 2.5%
    threshold: float          # dollar equivalent of pct at this ref: R * pct
    up_level: float           # ref_price * (1 + pct)
    down_level: float         # ref_price * (1 - pct)
    sess_high: float          # scan-day session high (max of 1-min bar highs)
    sess_low: float           # scan-day session low  (min of 1-min bar lows)
    max_up_swing: float       # sess_high - ref_price  (dollars)
    max_down_swing: float     # ref_price - sess_low   (dollars)
    max_up_swing_pct: float   # (sess_high - ref_price) / ref_price
    max_down_swing_pct: float # (ref_price - sess_low) / ref_price
    touched_up: bool          # any bar high >= up_level
    touched_down: bool        # any bar low  <= down_level

    @property
    def touched_both(self) -> bool:
        return self.touched_up and self.touched_down

    @property
    def touched_neither(self) -> bool:
        return not self.touched_up and not self.touched_down


@dataclass
class DataPullDetail:
    """One (date, strike) data-pull record, for full provenance reporting."""
    date: str
    strike: float
    contract_symbol: str
    source: str            # one of SOURCE_* above
    n_bars: int            # number of intraday price points obtained
    spot_at_3pm: float = 0.0
    sigma_used: float = 0.0   # only meaningful for simulation
    note: str = ''


@dataclass
class BacktestResult:
    ticker: str
    best_entry_minute: int
    best_exit_minute: int
    win_rate: float
    avg_payoff: float
    score: float
    n_dates: int
    all_pairs: list = field(default_factory=list)

    # ── Data provenance (so you can tell real vs simulated at a glance) ──
    n_real_pulls: int = 0          # pulls backed by real Alpaca option bars
    n_sim_pulls: int = 0           # pulls that fell back to BS simulation
    n_skipped_dates: int = 0       # MWF dates with no stock bars at all
    n_total_samples: int = 0       # total payoff samples feeding the stats
    primary_source: str = ''       # 'REAL', 'SIMULATED', 'MIXED', or 'NONE'
    sim_sigma: float = 0.0         # realized vol used for any simulation
    pull_details: list = field(default_factory=list)  # list[DataPullDetail]


@dataclass
class TradeRecord:
    date: str
    ticker: str
    strike: float
    expiry: str
    entry_time: str
    exit_time: str
    premium_paid: float
    contract_symbol: str = ''
    exit_price: float = 0.0
    payoff: float = 0.0
    profitable: bool = False
