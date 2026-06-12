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
