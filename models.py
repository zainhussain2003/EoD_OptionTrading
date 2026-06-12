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
