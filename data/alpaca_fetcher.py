import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from models import OptionContract
from utils.date_utils import ET, UTC, format_contract_symbol, window_start_utc, window_end_utc
from utils.math_utils import calc_theta_hourly

try:
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.requests import (
        StockBarsRequest,
        StockLatestQuoteRequest,
        OptionChainRequest,
        OptionBarsRequest,
    )
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


class AlpacaFetcher:
    def __init__(self, api_key: str, secret_key: str):
        if not ALPACA_AVAILABLE:
            raise RuntimeError("alpaca-py not installed. Run: pip install alpaca-py")
        self._stock_client = StockHistoricalDataClient(api_key, secret_key)
        self._option_client = OptionHistoricalDataClient(api_key, secret_key)

    @classmethod
    def from_env(cls) -> 'AlpacaFetcher | None':
        api_key = os.getenv('ALPACA_API_KEY', '')
        secret_key = os.getenv('ALPACA_API_SECRET', '')
        if not api_key or not secret_key:
            return None
        try:
            return cls(api_key, secret_key)
        except Exception:
            return None

    def fetch_spot_price(self, ticker: str) -> float:
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=[ticker])
            quotes = self._stock_client.get_stock_latest_quote(req)
            q = quotes[ticker]
            mid = (q.ask_price + q.bid_price) / 2.0
            return mid if mid > 0 else q.ask_price
        except Exception:
            end = datetime.now(UTC)
            start = end - timedelta(minutes=5)
            bars = self.fetch_historical_stock_bars(ticker, start, end, minutes=1)
            if bars is not None and not bars.empty:
                return float(bars['close'].iloc[-1])
            raise

    def fetch_option_chain(self, ticker: str, expiry_date: date,
                            risk_free_rate: float = 0.05) -> list[OptionContract]:
        """Fetch live put option chain with greeks."""
        contracts = []
        try:
            req = OptionChainRequest(
                underlying_symbol=ticker,
                expiration_date=expiry_date,
                type='put',
                feed='indicative',
            )
            chain = self._option_client.get_option_chain(req)
        except Exception:
            return contracts

        for symbol, snapshot in chain.items():
            try:
                bid = float(getattr(snapshot.latest_quote, 'bid_price', 0) or 0)
                ask = float(getattr(snapshot.latest_quote, 'ask_price', 0) or 0)
                if bid <= 0 and ask <= 0:
                    continue
                mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else (bid or ask)

                iv = float(getattr(snapshot, 'implied_volatility', 0) or 0)
                volume = int(getattr(snapshot, 'volume', 0) or 0)
                oi = int(getattr(snapshot, 'open_interest', 0) or 0)

                greeks = getattr(snapshot, 'greeks', None)
                delta = float(getattr(greeks, 'delta', 0) or 0) if greeks else 0.0
                theta = float(getattr(greeks, 'theta', 0) or 0) if greeks else 0.0
                theta_hourly = theta / 6.5 if theta != 0 else 0.0

                # Parse strike from symbol
                strike_str = symbol[-8:]
                strike = int(strike_str) / 1000.0

                contracts.append(OptionContract(
                    ticker=ticker,
                    contract_symbol=symbol,
                    strike=strike,
                    expiry=expiry_date,
                    bid=bid,
                    ask=ask,
                    mid_price=mid,
                    volume=volume,
                    open_interest=oi,
                    implied_volatility=iv,
                    delta=delta,
                    theta_hourly=theta_hourly,
                    in_the_money=(strike > getattr(snapshot, 'underlying_price', strike - 1)),
                ))
            except Exception:
                continue

        return contracts

    def fetch_historical_stock_bars(self, ticker: str, start: datetime, end: datetime,
                                     minutes: int = 5) -> pd.DataFrame | None:
        """Fetch stock OHLCV bars. Returns DataFrame with UTC index, or None on error."""
        try:
            timeframe = TimeFrame(minutes, TimeFrameUnit.Minute)
            req = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=timeframe,
                start=start,
                end=end,
                adjustment='raw',
                feed='iex',
            )
            bars = self._stock_client.get_stock_bars(req)
            df = bars.df
            if df.empty:
                return None
            # Drop multi-index symbol level if present
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(ticker, level='symbol')
            df.index = pd.to_datetime(df.index, utc=True)
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception:
            return None

    def fetch_historical_option_bars(self, contract_symbol: str,
                                      start: datetime, end: datetime) -> pd.DataFrame | None:
        """Fetch 1m option OHLCV bars. Returns DataFrame with UTC index, or None."""
        try:
            req = OptionBarsRequest(
                symbol_or_symbols=contract_symbol,
                timeframe=TimeFrame(1, TimeFrameUnit.Minute),
                start=start,
                end=end,
                feed='indicative',
            )
            bars = self._option_client.get_option_bars(req)
            df = bars.df
            if df.empty:
                return None
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(contract_symbol, level='symbol')
            df.index = pd.to_datetime(df.index, utc=True)
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception:
            return None
