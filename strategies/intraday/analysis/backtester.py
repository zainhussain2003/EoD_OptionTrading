import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd

from config import Config
from models import SOURCE_REAL, SOURCE_SIM, SOURCE_NO_STOCK
from utils.date_utils import (
    ET, get_past_weekday_dates, expiry_for, is_trading_day,
    trading_hours_until_close, detect_strike_interval, get_atm_strikes,
    format_contract_symbol, window_minute_utc,
)
from utils.math_utils import black_scholes_call, black_scholes_put, realized_vol


class Backtester:
    """Captures full-day (9:30 AM–4:00 PM) 1-minute option prices for every past
    session of the configured ENTRY WEEKDAY (config.entry_weekday), for BOTH the
    ATM call and the ATM put, trading the option that expires on
    config.expiry_weekday in the same week (0DTE when the two are equal, 1DTE
    otherwise; a holiday expiry rolls back one trading day). When no real option
    bars exist for that expiry it falls back to Black-Scholes simulation. The
    time-frame engine then aggregates those minutes into arbitrary frames and
    searches for the optimal intraday entry/exit windows. Nothing here picks a
    schedule — it only fetches data.

    daily_capture is keyed by (ticker, opt_type) where opt_type is 'C' or 'P'.
    Each record is {date, strike, contract, source, spot_open, prices, note}
    with prices = {minute_of_day: close_price}.
    """

    def __init__(self, fetcher, config: Config):
        self.fetcher = fetcher
        self.config = config
        self.daily_capture: dict = defaultdict(list)

    def run(self, tickers: list[str] | None = None) -> None:
        tickers = tickers or self.config.tickers
        for ticker in tickers:
            print(f"  Backtesting {ticker}...", flush=True)
            self._capture_ticker(ticker)

    def _capture_ticker(self, ticker: str) -> None:
        entry_wd = self.config.entry_weekday
        exp_wd = self.config.expiry_weekday
        past_dates = get_past_weekday_dates(entry_wd, self.config.backtest_days)
        dte_label = '0DTE' if exp_wd == entry_wd else '1DTE'

        # Daily closes feed realized vol for any Black-Scholes simulation fallback.
        daily_closes = []
        if hasattr(self.fetcher, 'get_daily_closes'):
            daily_closes = self.fetcher.get_daily_closes(ticker, days=40)
        sim_sigma = realized_vol(daily_closes) if len(daily_closes) >= 10 else 0.35
        sim_sigma = max(0.10, min(2.0, sim_sigma))

        opt_types = self.config.option_types
        start_m = self.config.window_start_minute
        end_m = self.config.window_end_minute

        for entry_d in past_dates:
            # The expiry we trade: the configured expiry weekday in the same week
            # (rolled back a session if it is a holiday).
            exp_date = expiry_for(entry_d, exp_wd)
            win_start = window_minute_utc(entry_d, start_m)
            win_end = window_minute_utc(entry_d, end_m)

            # Closed entry day (holiday) → no session this week.
            if not is_trading_day(entry_d):
                for ot in opt_types:
                    self.daily_capture[(ticker, ot)].append({
                        'date': entry_d, 'strike': 0.0, 'contract': '',
                        'source': SOURCE_NO_STOCK, 'spot_open': 0.0, 'prices': {},
                        'note': 'missing data (entry-day market holiday)',
                    })
                continue

            # Full-day stock bars to determine the ATM strike at the open.
            stock_bars = self.fetcher.fetch_historical_stock_bars(
                ticker, win_start, win_end, minutes=1)
            if stock_bars is None or stock_bars.empty:
                stock_bars = self.fetcher.fetch_historical_stock_bars(
                    ticker, win_start, win_end, minutes=5)

            if stock_bars is None or stock_bars.empty:
                for ot in opt_types:
                    self.daily_capture[(ticker, ot)].append({
                        'date': entry_d, 'strike': 0.0, 'contract': '',
                        'source': SOURCE_NO_STOCK, 'spot_open': 0.0, 'prices': {},
                        'note': 'missing data (no entry-day stock bars)',
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
                    else:
                        minute_prices = self._simulate_option_prices(
                            stock_bars, atm_strike, exp_date, ot, sim_sigma)
                        source = SOURCE_SIM

                    if not minute_prices:
                        continue

                    self.daily_capture[(ticker, ot)].append({
                        'date': entry_d,            # bucket by the entry day
                        'strike': atm_strike,
                        'contract': contract_sym,   # encodes the expiry date used
                        'source': source,
                        'spot_open': spot_open,
                        'prices': dict(minute_prices),
                        'note': (f'{dte_label} (expiry {exp_date:%a %m-%d})'
                                 if exp_date != entry_d
                                 else f'{dte_label} (same-day expiry)'),
                    })
                    captured_any = True

                if not captured_any:
                    self.daily_capture[(ticker, ot)].append({
                        'date': entry_d, 'strike': 0.0, 'contract': '',
                        'source': SOURCE_NO_STOCK, 'spot_open': spot_open,
                        'prices': {}, 'note': 'missing data (no option prices)',
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
        """Simulate intraday option prices via Black-Scholes from stock history.

        Time-to-expiry counts TRADING hours to the expiry 4 PM close (via
        trading_hours_until_close), so a 1DTE option keeps its overnight time
        value instead of decaying across the closed hours (0DTE decays to 0).
        """
        prices = {}
        r = self.config.risk_free_rate
        start_m = self.config.window_start_minute
        end_m = self.config.window_end_minute
        bs = black_scholes_call if opt_type == 'C' else black_scholes_put
        # Fractional-trading-year floor of ~1 trading minute.
        T_FLOOR = 1.0 / (252.0 * 6.5 * 60.0)

        for ts, row in stock_bars.iterrows():
            et_ts = pd.Timestamp(ts).tz_convert(ET)
            m = et_ts.hour * 60 + et_ts.minute
            if not (start_m <= m < end_m):
                continue

            spot = float(row['close'])
            hours_left = trading_hours_until_close(et_ts.to_pydatetime(), expiry_date)
            T = max(hours_left / (252.0 * 6.5), T_FLOOR)

            bs_price, _, _, _ = bs(spot, strike, T, r, sigma)
            prices[m] = max(bs_price, 0.0)

        return prices
