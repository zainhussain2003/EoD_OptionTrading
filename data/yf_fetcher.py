import time
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from models import OptionContract
from utils.date_utils import ET, UTC, window_start_utc, window_end_utc
from utils.math_utils import (
    black_scholes_put, calc_pop, calc_theta_hourly, realized_vol
)


def _compute_T(expiry_date: date, now_dt: datetime) -> float:
    from utils.date_utils import compute_T
    return compute_T(expiry_date, now_dt)


class YFinanceFetcher:
    """yfinance-based fetcher. Always available, no API key needed."""

    def fetch_spot_price(self, ticker: str) -> float:
        t = yf.Ticker(ticker)
        df = t.history(period='1d', interval='1m')
        if df.empty:
            info = t.info
            return float(info.get('regularMarketPrice') or info.get('currentPrice', 0))
        return float(df['Close'].iloc[-1])

    def fetch_option_chain(self, ticker: str, expiry_date: date,
                            risk_free_rate: float = 0.05) -> list[OptionContract]:
        """Fetch put option chain via yfinance. Greeks computed via Black-Scholes."""
        contracts = []
        date_str = expiry_date.strftime('%Y-%m-%d')
        t = yf.Ticker(ticker)

        for attempt in range(3):
            try:
                chain = t.option_chain(date_str)
                df = chain.puts
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)
                else:
                    return contracts

        if df is None or df.empty:
            return contracts

        try:
            spot = self.fetch_spot_price(ticker)
        except Exception:
            spot = 0.0

        now_dt = datetime.now(ET)

        for _, row in df.iterrows():
            try:
                bid = float(row.get('bid', 0) or 0)
                ask = float(row.get('ask', 0) or 0)
                if bid < 0:
                    bid = 0.0
                if ask < 0:
                    ask = 0.0
                if bid == 0 and ask == 0:
                    continue
                mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else (ask or bid)

                iv = float(row.get('impliedVolatility', 0) or 0)
                if iv <= 0 or iv > 5.0:
                    continue

                volume = int(row.get('volume', 0) or 0)
                oi = int(row.get('openInterest', 0) or 0)
                strike = float(row['strike'])

                T = _compute_T(expiry_date, now_dt)
                _, delta, _, _ = black_scholes_put(spot, strike, T, risk_free_rate, iv)
                theta_h = calc_theta_hourly(spot, strike, T, risk_free_rate, iv)

                contracts.append(OptionContract(
                    ticker=ticker,
                    contract_symbol=str(row.get('contractSymbol', '')),
                    strike=strike,
                    expiry=expiry_date,
                    bid=bid,
                    ask=ask,
                    mid_price=mid,
                    volume=volume,
                    open_interest=oi,
                    implied_volatility=iv,
                    delta=delta,
                    theta_hourly=theta_h,
                    in_the_money=bool(row.get('inTheMoney', False)),
                ))
            except Exception:
                continue

        return contracts

    def fetch_historical_stock_bars(self, ticker: str, start: datetime, end: datetime,
                                     minutes: int = 5) -> pd.DataFrame | None:
        """Fetch stock bars from yfinance. Converts index to UTC."""
        try:
            t = yf.Ticker(ticker)
            period_days = (end - start).days + 1
            if period_days <= 7:
                interval = '1m'
            elif period_days <= 60:
                interval = '5m'
            else:
                interval = '1h'

            df = t.history(start=start, end=end, interval=interval)
            if df.empty:
                return None
            df.index = pd.to_datetime(df.index, utc=True)
            df.columns = [c.lower() for c in df.columns]
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception:
            return None

    def fetch_historical_option_bars(self, contract_symbol: str,
                                      start: datetime, end: datetime) -> pd.DataFrame | None:
        """yfinance has no historical option bars — always returns None (triggers BS sim)."""
        return None

    def get_mwf_expiry_dates(self, ticker: str, max_count: int = 3) -> list[date]:
        """Return up to max_count nearest MWF expiry dates from ticker.options."""
        from utils.date_utils import MWF
        try:
            t = yf.Ticker(ticker)
            available = t.options
        except Exception:
            return []

        today = date.today()
        mwf_dates = []
        for ds in available:
            try:
                d = date.fromisoformat(ds)
                if d >= today and d.weekday() in MWF:
                    mwf_dates.append(d)
                    if len(mwf_dates) >= max_count:
                        break
            except ValueError:
                continue
        return sorted(mwf_dates)

    def get_daily_closes(self, ticker: str, days: int = 30) -> list[float]:
        """Fetch recent daily closing prices for realized vol calculation."""
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=f'{days}d', interval='1d')
            return [float(c) for c in df['Close'].dropna().tolist()]
        except Exception:
            return []
