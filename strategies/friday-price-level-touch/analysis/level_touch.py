"""
Core analysis for the Friday price-level-touch study.

For every past Friday in the lookback window, and for each ticker:

  1. BASELINE — fetch the preceding Thursday's 1-minute stock bars and read the
     close at each of the reference minutes 3:50, 3:51, 3:52, 3:53, 3:54, 3:55 PM
     ET. A 7th "3:50–55 avg" baseline is the mean of those available closes.
     If Thursday is a market holiday, step back to the nearest preceding trading
     day (Wed, Tue …) and note the substitution.

  2. SCAN — fetch Friday's full regular session (9:30 AM–4:00 PM ET) 1-minute
     bars and take the session high (max of bar highs) and low (min of bar lows).

  3. TOUCH / SWING — for each reference price R and the ticker's dollar threshold:
        up_level   = R + threshold     down_level = R - threshold
        touched_up   = fri_high >= up_level      (any intraday bar high reaches it)
        touched_down = fri_low  <= down_level    (any intraday bar low  reaches it)
        max_up_swing   = fri_high - R
        max_down_swing = R - fri_low

Nothing here trades or prices options — it only measures how far Friday travels
from Thursday's near-close baseline. The engine aggregates these records into the
per-ticker / per-reference hit-rate tables and the steadiest-baseline summary.
"""
import time
from datetime import timedelta

import pandas as pd

from config import Config
from models import FridayLevelRecord
from utils.date_utils import ET, get_past_friday_dates, window_minute_utc, minute_to_str

# A Friday needs at least this many 1-minute bars to count as a tradeable session.
MIN_FRIDAY_BARS = 30
# How many calendar days to step back from Friday looking for a baseline day with
# 3:50–3:55 PM data (Thursday normally; Wednesday/Tuesday on a Thursday holiday).
MAX_BASELINE_LOOKBACK = 4
AVG_LABEL = '3:50–55 avg'


def _bars_to_minute_ohlc(bars, start_m: int, end_m: int) -> dict:
    """{minute_of_day: (high, low, close)} for bars inside [start_m, end_m) ET."""
    out = {}
    if bars is None or bars.empty:
        return out
    for ts, row in bars.iterrows():
        et_ts = pd.Timestamp(ts).tz_convert(ET)
        m = et_ts.hour * 60 + et_ts.minute
        if start_m <= m < end_m:
            out[m] = (float(row['high']), float(row['low']), float(row['close']))
    return out


class LevelTouchAnalyzer:
    """Captures Thursday baselines + Friday sessions and builds the per-Friday
    touch/swing records for every ticker. Mirrors the role of analysis.Backtester
    in the time-frame study, but for stock price levels rather than option P&L."""

    def __init__(self, fetcher, config: Config):
        self.fetcher = fetcher
        self.config = config

    def run(self, tickers=None) -> dict:
        tickers = tickers or list(self.config.ticker_thresholds.keys())
        return {t: self.analyze(t) for t in tickers}

    # ── per-Friday fetch helpers ─────────────────────────────────────────────
    def _fetch_friday_session(self, ticker, friday):
        """Friday 9:30 AM–4:00 PM 1-min bars → {minute: (high, low, close)}."""
        start_m = self.config.friday_start_minute
        end_m = self.config.friday_end_minute
        win_start = window_minute_utc(friday, start_m)
        win_end = window_minute_utc(friday, end_m)
        bars = self.fetcher.fetch_historical_stock_bars(
            ticker, win_start, win_end, minutes=self.config.bar_minutes)
        return _bars_to_minute_ohlc(bars, start_m, end_m)

    def _fetch_thursday_refs(self, ticker, friday):
        """Walk back from Friday to the nearest trading day with 3:50–3:55 PM data.

        Returns (baseline_date, {ref_minute: close_price}) or (None, {})."""
        ref_minutes = self.config.thursday_ref_minutes
        lo, hi = min(ref_minutes), max(ref_minutes)
        for back in range(1, MAX_BASELINE_LOOKBACK + 1):
            day = friday - timedelta(days=back)
            if day.weekday() >= 5:          # skip weekends entirely
                continue
            win_start = window_minute_utc(day, lo - 2)     # small pad for alignment
            win_end = window_minute_utc(day, hi + 2)
            bars = self.fetcher.fetch_historical_stock_bars(
                ticker, win_start, win_end, minutes=self.config.bar_minutes)
            ohlc = _bars_to_minute_ohlc(bars, lo, hi + 1)
            refs = {m: ohlc[m][2] for m in ref_minutes if m in ohlc}  # close price
            if refs:
                return day, refs
        return None, {}

    # ── main per-ticker analysis ─────────────────────────────────────────────
    def analyze(self, ticker: str) -> dict:
        threshold = float(self.config.ticker_thresholds[ticker])
        ref_minutes = self.config.thursday_ref_minutes
        single_labels = [minute_to_str(m) for m in ref_minutes]
        ref_labels = list(single_labels)
        if self.config.include_avg_baseline:
            ref_labels.append(AVG_LABEL)

        print(f"  Analyzing {ticker} (threshold ±${threshold:.2f})...", flush=True)

        records: list[FridayLevelRecord] = []
        per_friday_refs: dict = {}        # {date_str: {single_label: price}} for steadiness
        skipped: list[str] = []
        n_fridays = 0
        n_baseline_substituted = 0

        for friday in get_past_friday_dates(self.config.backtest_days):
            fri_ohlc = self._fetch_friday_session(ticker, friday)
            if len(fri_ohlc) < MIN_FRIDAY_BARS:
                skipped.append(f"{friday} (Friday closed/sparse)")
                time.sleep(0.2)
                continue

            base_date, refs = self._fetch_thursday_refs(ticker, friday)
            if not refs:
                skipped.append(f"{friday} (no Thursday baseline)")
                time.sleep(0.2)
                continue

            fri_high = max(v[0] for v in fri_ohlc.values())
            fri_low = min(v[1] for v in fri_ohlc.values())
            substituted = (base_date != friday - timedelta(days=1))
            if substituted:
                n_baseline_substituted += 1

            # Build the reference-price map: each single minute + the avg.
            ref_price_by_label = {minute_to_str(m): refs[m] for m in ref_minutes if m in refs}
            per_friday_refs[str(friday)] = dict(ref_price_by_label)
            if self.config.include_avg_baseline and refs:
                ref_price_by_label[AVG_LABEL] = sum(refs.values()) / len(refs)

            for label in ref_labels:
                R = ref_price_by_label.get(label)
                if R is None:               # this single minute had no bar that week
                    continue
                up_level = R + threshold
                down_level = R - threshold
                records.append(FridayLevelRecord(
                    date=str(friday), ticker=ticker, thu_ref_label=label,
                    thu_ref_price=round(R, 4), threshold=threshold,
                    up_level=round(up_level, 4), down_level=round(down_level, 4),
                    fri_high=round(fri_high, 4), fri_low=round(fri_low, 4),
                    max_up_swing=round(fri_high - R, 4),
                    max_down_swing=round(R - fri_low, 4),
                    touched_up=bool(fri_high >= up_level),
                    touched_down=bool(fri_low <= down_level),
                ))
            n_fridays += 1
            time.sleep(0.2)               # rate-limit courtesy pause

        return {
            "ticker": ticker,
            "threshold": threshold,
            "ref_labels": ref_labels,
            "single_labels": single_labels,
            "records": records,
            "per_friday_refs": per_friday_refs,
            "n_fridays": n_fridays,
            "n_skipped": len(skipped),
            "skipped_dates": skipped,
            "n_baseline_substituted": n_baseline_substituted,
        }
