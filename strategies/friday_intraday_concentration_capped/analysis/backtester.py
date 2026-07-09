import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd

from config import Config
from models import SOURCE_REAL, SOURCE_SIM, SOURCE_NO_STOCK
from utils.date_utils import (
    ET, get_past_friday_dates, detect_strike_interval, get_atm_strikes,
    format_contract_symbol, window_minute_utc,
)
from utils.math_utils import black_scholes_call, black_scholes_put, realized_vol


class Backtester:
    """Captures full-day (9:30 AM–4:00 PM) 1-minute option prices for every past
    Friday, for BOTH the ATM call and the ATM put. The time-frame engine then
    aggregates those minutes into arbitrary frames and searches for the optimal
    entry/exit windows. Nothing here picks a schedule — it only fetches data.

    daily_capture is keyed by (ticker, opt_type) where opt_type is 'C' or 'P'.
    Each record is {date, strike, contract, source, spot_open, prices, note}
    with prices = {minute_of_day: close_price}.
    """

    def __init__(self, fetcher, config: Config):
        self.fetcher = fetcher
        self.config = config
        # When True, a Friday with no data (market closed) falls back to the
        # preceding Thursday's REAL data/expiry (the weekly option moves to
        # Thursday). Real-only on that fallback — never simulated.
        self.friday_thursday_fallback = True
        self.daily_capture: dict = defaultdict(list)

    def run(self, tickers: list[str] | None = None) -> None:
        tickers = tickers or self.config.tickers
        for ticker in tickers:
            print(f"  Backtesting {ticker}...", flush=True)
            self._capture_ticker(ticker)

    def _capture_ticker(self, ticker: str) -> None:
        past_dates = get_past_friday_dates(self.config.backtest_days)

        # Daily closes feed realized vol for any Black-Scholes simulation fallback.
        daily_closes = []
        if hasattr(self.fetcher, 'get_daily_closes'):
            daily_closes = self.fetcher.get_daily_closes(ticker, days=40)
        sim_sigma = realized_vol(daily_closes) if len(daily_closes) >= 10 else 0.35
        sim_sigma = max(0.10, min(2.0, sim_sigma))

        opt_types = self.config.option_types
        start_m = self.config.window_start_minute
        end_m = self.config.window_end_minute

        for friday in past_dates:
            # exp_date = the date whose data/expiry we actually use. Normally the
            # Friday itself; for a closed Friday it falls back to Thursday.
            exp_date = friday
            real_only = False
            win_start = window_minute_utc(friday, start_m)
            win_end = window_minute_utc(friday, end_m)

            # Full-day stock bars to determine the ATM strike at the open.
            stock_bars = self.fetcher.fetch_historical_stock_bars(
                ticker, win_start, win_end, minutes=1)
            if stock_bars is None or stock_bars.empty:
                stock_bars = self.fetcher.fetch_historical_stock_bars(
                    ticker, win_start, win_end, minutes=5)

            # Closed Friday → use the preceding Thursday's REAL data/expiry.
            if ((stock_bars is None or stock_bars.empty)
                    and self.friday_thursday_fallback):
                thu = friday - timedelta(days=1)
                t_start = window_minute_utc(thu, start_m)
                t_end = window_minute_utc(thu, end_m)
                thu_bars = self.fetcher.fetch_historical_stock_bars(
                    ticker, t_start, t_end, minutes=1)
                if thu_bars is None or thu_bars.empty:
                    thu_bars = self.fetcher.fetch_historical_stock_bars(
                        ticker, t_start, t_end, minutes=5)
                if thu_bars is not None and not thu_bars.empty:
                    exp_date = thu
                    real_only = True
                    win_start, win_end = t_start, t_end
                    stock_bars = thu_bars

            if stock_bars is None or stock_bars.empty:
                # Surface the closed week as a "missing data" row for both types.
                for ot in opt_types:
                    self.daily_capture[(ticker, ot)].append({
                        'date': friday, 'strike': 0.0, 'contract': '',
                        'source': SOURCE_NO_STOCK, 'spot_open': 0.0, 'prices': {},
                        'note': 'missing data (Fri & Thu closed)',
                    })
                continue

            spot_open = float(stock_bars['close'].iloc[0])
            interval = detect_strike_interval(spot_open)
            lower_strike, upper_strike = get_atm_strikes(spot_open, interval)

            for ot in opt_types:
                captured_any = False
                for atm_strike in [lower_strike, upper_strike]:
                    contract_sym = format_contract_symbol(
                        ticker, exp_date, atm_strike, ot)

                    opt_bars = self.fetcher.fetch_historical_option_bars(
                        contract_sym, win_start, win_end)

                    if opt_bars is not None and len(opt_bars) >= 5:
                        minute_prices = self._bars_to_minute_prices(opt_bars)
                        source = SOURCE_REAL
                    elif real_only:
                        # Thursday fallback is real-only — do not simulate.
                        continue
                    else:
                        minute_prices = self._simulate_option_prices(
                            stock_bars, atm_strike, exp_date, ot, sim_sigma)
                        source = SOURCE_SIM

                    if not minute_prices:
                        continue

                    self.daily_capture[(ticker, ot)].append({
                        'date': friday,             # bucket by the nominal Friday
                        'strike': atm_strike,
                        'contract': contract_sym,   # encodes the real expiry used
                        'source': source,
                        'spot_open': spot_open,
                        'prices': dict(minute_prices),
                        'note': ('Fri closed → Thu expiry'
                                 if exp_date != friday else ''),
                    })
                    captured_any = True

                # Thursday existed but no REAL option bars → mark the week missing
                # (real-only fallback never simulates).
                if real_only and not captured_any:
                    self.daily_capture[(ticker, ot)].append({
                        'date': friday, 'strike': 0.0, 'contract': '',
                        'source': SOURCE_NO_STOCK, 'spot_open': spot_open,
                        'prices': {}, 'note': 'missing data (no real Thu option bars)',
                    })

            time.sleep(0.3)  # rate limit courtesy pause

    def _bars_to_minute_prices(self, bars: pd.DataFrame) -> dict[int, float]:
        """Convert a bar DataFrame to {minute_of_day: close_price} using ET time."""
        start_m = self.config.window_start_minute
        end_m = self.config.window_end_minute
        prices = {}
        for ts, row in bars.iterrows():
            et_ts = pd.Timestamp(ts).tz_convert(ET)
            m = et_ts.hour * 60 + et_ts.minute
            if start_m <= m < end_m:  # within the regular session
                prices[m] = float(row['close'])
        return prices

    def _simulate_option_prices(self, stock_bars: pd.DataFrame, strike: float,
                                 expiry_date: date, opt_type: str,
                                 sigma: float) -> dict[int, float]:
        """Simulate 0DTE option prices via Black-Scholes from stock price history."""
        prices = {}
        r = self.config.risk_free_rate
        start_m = self.config.window_start_minute
        end_m = self.config.window_end_minute
        bs = black_scholes_call if opt_type == 'C' else black_scholes_put

        for ts, row in stock_bars.iterrows():
            et_ts = pd.Timestamp(ts).tz_convert(ET)
            m = et_ts.hour * 60 + et_ts.minute
            if not (start_m <= m < end_m):
                continue

            spot = float(row['close'])
            # Option expires at the 4 PM market close (0DTE).
            close_et = datetime(expiry_date.year, expiry_date.month, expiry_date.day,
                                16, 0, 0, tzinfo=ET)
            bar_et = et_ts.to_pydatetime()
            seconds_left = max((close_et - bar_et).total_seconds(), 60)
            T = max(seconds_left / (252.0 * 6.5 * 3600.0), 1.0 / (252.0 * 6.5 * 60.0))

            bs_price, _, _, _ = bs(spot, strike, T, r, sigma)
            prices[m] = max(bs_price, 0.0)

        return prices
