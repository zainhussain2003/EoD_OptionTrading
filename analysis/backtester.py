import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd

from config import Config
from models import (
    BacktestPairResult, BacktestResult, DataPullDetail,
    SOURCE_REAL, SOURCE_SIM, SOURCE_NO_STOCK,
)
from utils.date_utils import (
    ET, UTC, get_past_mwf_dates, detect_strike_interval, get_atm_strikes,
    format_contract_symbol, window_start_utc, window_end_utc, minute_to_str
)
from utils.math_utils import black_scholes_put, realized_vol


class Backtester:
    def __init__(self, fetcher, config: Config):
        self.fetcher = fetcher
        self.config = config
        # Optional per-day capture (used by custom_backtest.py for day-by-day P&L).
        # Off by default so the standard --backtest path is unchanged.
        self.capture_daily = False
        self.daily_capture: dict = defaultdict(list)

    def run(self, tickers: list[str] | None = None) -> list[BacktestResult]:
        tickers = tickers or self.config.tickers
        results = []
        for ticker in tickers:
            print(f"  Backtesting {ticker}...", flush=True)
            result = self._backtest_ticker(ticker)
            results.append(result)
        return results

    def _backtest_ticker(self, ticker: str) -> BacktestResult:
        past_dates = get_past_mwf_dates(self.config.backtest_days)

        # payoffs[(entry_min, exit_min)] = [payoff1, payoff2, ...]
        payoffs: dict[tuple, list] = defaultdict(list)

        # Preload daily closes for realized vol (used by BS simulation)
        daily_closes = []
        if hasattr(self.fetcher, 'get_daily_closes'):
            daily_closes = self.fetcher.get_daily_closes(ticker, days=40)
        sim_sigma = realized_vol(daily_closes) if len(daily_closes) >= 10 else 0.35
        sim_sigma = max(0.10, min(2.0, sim_sigma))

        # Provenance tracking
        pull_details: list[DataPullDetail] = []
        n_real = 0
        n_sim = 0
        n_skipped = 0
        dates_used = 0

        for mwf_date in past_dates:
            win_start = window_start_utc(mwf_date)
            win_end = window_end_utc(mwf_date)

            # Get stock bars for the 3-4 PM window to determine ATM strike
            stock_bars = self.fetcher.fetch_historical_stock_bars(
                ticker, win_start, win_end, minutes=1
            )
            if stock_bars is None or stock_bars.empty:
                # Try 5m as fallback
                stock_bars = self.fetcher.fetch_historical_stock_bars(
                    ticker, win_start, win_end, minutes=5
                )
            if stock_bars is None or stock_bars.empty:
                n_skipped += 1
                pull_details.append(DataPullDetail(
                    date=str(mwf_date), strike=0.0, contract_symbol='',
                    source=SOURCE_NO_STOCK, n_bars=0,
                    note='no stock bars in 3-4 PM window',
                ))
                continue

            # Spot price at start of window for ATM strike determination
            spot_3pm = float(stock_bars['close'].iloc[0])
            interval = detect_strike_interval(spot_3pm)
            lower_strike, upper_strike = get_atm_strikes(spot_3pm, interval)

            # Try both ATM strikes, use the one we can get data for
            for atm_strike in [lower_strike, upper_strike]:
                contract_sym = format_contract_symbol(ticker, mwf_date, atm_strike)

                # Try real option bars first
                opt_bars = self.fetcher.fetch_historical_option_bars(
                    contract_sym, win_start, win_end
                )

                if opt_bars is not None and len(opt_bars) >= 5:
                    minute_prices = self._bars_to_minute_prices(opt_bars)
                    source = SOURCE_REAL
                    n_real += 1
                    detail_sigma = 0.0
                else:
                    # Simulate using Black-Scholes + stock prices
                    minute_prices = self._simulate_option_prices(
                        stock_bars, atm_strike, mwf_date, daily_closes
                    )
                    source = SOURCE_SIM
                    n_sim += 1
                    detail_sigma = sim_sigma

                pull_details.append(DataPullDetail(
                    date=str(mwf_date), strike=atm_strike,
                    contract_symbol=contract_sym, source=source,
                    n_bars=len(minute_prices), spot_at_3pm=spot_3pm,
                    sigma_used=detail_sigma,
                ))

                if not minute_prices:
                    continue

                if self.capture_daily:
                    self.daily_capture[ticker].append({
                        'date': mwf_date,
                        'strike': atm_strike,
                        'contract': contract_sym,
                        'source': source,
                        'spot_3pm': spot_3pm,
                        'prices': dict(minute_prices),
                    })

                self._accumulate_payoffs(minute_prices, payoffs, prefix=(atm_strike,))

            dates_used += 1
            time.sleep(0.3)  # rate limit courtesy pause

        result = self._build_result(ticker, payoffs, dates_used)

        # Attach provenance
        result.n_real_pulls = n_real
        result.n_sim_pulls = n_sim
        result.n_skipped_dates = n_skipped
        result.n_total_samples = sum(len(v) for v in payoffs.values())
        result.sim_sigma = sim_sigma
        result.pull_details = pull_details
        if n_real > 0 and n_sim == 0:
            result.primary_source = 'REAL'
        elif n_sim > 0 and n_real == 0:
            result.primary_source = 'SIMULATED'
        elif n_real > 0 and n_sim > 0:
            result.primary_source = 'MIXED'
        else:
            result.primary_source = 'NONE'

        return result

    def _bars_to_minute_prices(self, bars: pd.DataFrame) -> dict[int, float]:
        """Convert bar DataFrame to {minute_of_day: close_price} using ET time."""
        prices = {}
        for ts, row in bars.iterrows():
            et_ts = pd.Timestamp(ts).tz_convert(ET)
            m = et_ts.hour * 60 + et_ts.minute
            if 900 <= m < 960:  # 3:00 PM to 3:59 PM
                prices[m] = float(row['close'])
        return prices

    def _simulate_option_prices(self, stock_bars: pd.DataFrame, strike: float,
                                 expiry_date: date, daily_closes: list[float]) -> dict[int, float]:
        """Simulate put option prices via Black-Scholes using stock price history."""
        sigma = realized_vol(daily_closes) if len(daily_closes) >= 10 else 0.35
        sigma = max(0.10, min(2.0, sigma))

        prices = {}
        r = self.config.risk_free_rate

        for ts, row in stock_bars.iterrows():
            et_ts = pd.Timestamp(ts).tz_convert(ET)
            m = et_ts.hour * 60 + et_ts.minute
            if not (900 <= m < 960):
                continue

            spot = float(row['close'])
            close_et = datetime(expiry_date.year, expiry_date.month, expiry_date.day,
                                16, 0, 0, tzinfo=ET)
            bar_et = et_ts.to_pydatetime()
            seconds_left = max((close_et - bar_et).total_seconds(), 60)
            T = max(seconds_left / (252.0 * 6.5 * 3600.0), 1.0 / (252.0 * 6.5 * 60.0))

            bs_price, _, _, _ = black_scholes_put(spot, strike, T, r, sigma)
            prices[m] = max(bs_price, 0.0)

        return prices

    def _accumulate_payoffs(self, minute_prices: dict[int, float],
                             payoffs: dict, prefix: tuple) -> None:
        step = self.config.entry_step_minutes
        min_hold = self.config.min_hold_minutes
        sorted_minutes = sorted(minute_prices.keys())

        for entry_m in range(900, 951, step):  # 3:00 to 3:50
            if entry_m not in minute_prices:
                # Use nearest available bar
                candidates = [m for m in sorted_minutes if abs(m - entry_m) <= step]
                if not candidates:
                    continue
                entry_m_actual = min(candidates, key=lambda m: abs(m - entry_m))
            else:
                entry_m_actual = entry_m

            premium = minute_prices[entry_m_actual]
            if premium <= 0:
                continue

            for exit_m in range(entry_m + min_hold, 960, step):  # entry+min_hold to 3:59
                if exit_m not in minute_prices:
                    candidates = [m for m in sorted_minutes if abs(m - exit_m) <= step and m > entry_m_actual]
                    if not candidates:
                        continue
                    exit_m_actual = min(candidates, key=lambda m: abs(m - exit_m))
                else:
                    exit_m_actual = exit_m

                exit_price = minute_prices[exit_m_actual]
                payoff = exit_price - premium
                key = (entry_m, exit_m)
                payoffs[key].append(payoff)

    def _build_result(self, ticker: str, payoffs: dict,
                       n_dates: int) -> BacktestResult:
        all_pairs = []
        best_score = -float('inf')
        best_entry = 900
        best_exit = 955

        for (entry_m, exit_m), plist in payoffs.items():
            if len(plist) < 3:  # need at least 3 samples to be meaningful
                continue
            wins = sum(1 for p in plist if p > 0)
            win_rate = wins / len(plist)
            avg_payoff = sum(plist) / len(plist)
            # Score: win_rate weighted by avg_payoff (positive bias)
            score = win_rate * max(avg_payoff, 0.0) + win_rate * 0.001
            all_pairs.append(BacktestPairResult(
                entry_minute=entry_m,
                exit_minute=exit_m,
                win_rate=win_rate,
                avg_payoff=avg_payoff,
                score=score,
                n_trades=len(plist),
            ))
            if score > best_score:
                best_score = score
                best_entry = entry_m
                best_exit = exit_m
                best_win_rate = win_rate
                best_avg_payoff = avg_payoff

        if not all_pairs:
            best_win_rate = 0.0
            best_avg_payoff = 0.0
            best_score = 0.0

        all_pairs.sort(key=lambda p: p.score, reverse=True)

        return BacktestResult(
            ticker=ticker,
            best_entry_minute=best_entry,
            best_exit_minute=best_exit,
            win_rate=best_win_rate if all_pairs else 0.0,
            avg_payoff=best_avg_payoff if all_pairs else 0.0,
            score=best_score if all_pairs else 0.0,
            n_dates=n_dates,
            all_pairs=all_pairs,
        )
