"""
Core analysis for the Mon/Wed/Fri price-level-touch (percentage) study.

For each scan day (Monday, Wednesday, Friday) in the lookback window, and for each
ticker:

  1. BASELINE — fetch the prior trading day's 1-minute stock bars and read the
     close at each of the reference minutes 3:50, 3:51, 3:52, 3:53, 3:54, 3:55 PM
     ET. A 7th "3:50–55 avg" baseline is the mean of those available closes. The
     prior trading day is the weekday immediately before the scan day (Monday ←
     prior Friday, Wednesday ← Tuesday, Friday ← Thursday); if that day is a market
     holiday, step back to the nearest preceding trading day and note the
     substitution.

  2. SCAN — fetch the scan day's full regular session (9:30 AM–4:00 PM ET) 1-minute
     bars and take the session high (max of bar highs) and low (min of bar lows).

  3. TOUCH / SWING — for each baseline price R and each percentage threshold pct in
     the ticker's list (e.g. 1%, 1.5%, 2%, 2.5%, 3%):
        up_level   = R * (1 + pct)     down_level = R * (1 - pct)
        touched_up   = sess_high >= up_level     (any intraday bar high reaches it)
        touched_down = sess_low  <= down_level   (any intraday bar low  reaches it)
        max_up_swing   = sess_high - R   (also as a % of R: (sess_high - R) / R)
        max_down_swing = R - sess_low    (also as a % of R: (R - sess_low) / R)

     The max-up / max-down swing is the biggest distance the scan day travelled
     from R in each direction; it depends only on R and the day's high/low, not on
     pct, so it is identical across a ticker's percentage thresholds.

Nothing here trades or prices options — it only measures how far each scan day
travels from the prior day's near-close baseline (real stock prices). The engine
aggregates these records into the per-ticker / per-day / per-reference hit-rate
tables, the steadiest-baseline summary, and the combined day comparison.
"""
import time
from datetime import timedelta

import pandas as pd

from config import Config
from models import LevelTouchRecord
from utils.date_utils import (ET, WEEKDAY_NUM, get_past_weekday_dates,
                              prior_trading_weekday, window_minute_utc, minute_to_str)

# A session needs at least this many 1-minute bars to count as tradeable.
MIN_SESSION_BARS = 30
# How many calendar days to step back from the scan day looking for a baseline day
# with 3:50–3:55 PM data. Monday's baseline (prior Friday) is 3 calendar days back,
# so the window must comfortably exceed a long weekend plus a holiday.
MAX_BASELINE_LOOKBACK = 6
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
    """Captures prior-day baselines + scan-day sessions and builds the per-day
    touch/swing records for every ticker across Monday, Wednesday and Friday."""

    def __init__(self, fetcher, config: Config):
        self.fetcher = fetcher
        self.config = config

    def run(self, tickers=None) -> dict:
        tickers = tickers or list(self.config.ticker_pcts.keys())
        return {t: self.analyze(t) for t in tickers}

    # ── per-session fetch helpers ────────────────────────────────────────────
    def _fetch_session(self, ticker, day):
        """Scan-day 9:30 AM–4:00 PM 1-min bars → {minute: (high, low, close)}."""
        start_m = self.config.friday_start_minute
        end_m = self.config.friday_end_minute
        win_start = window_minute_utc(day, start_m)
        win_end = window_minute_utc(day, end_m)
        bars = self.fetcher.fetch_historical_stock_bars(
            ticker, win_start, win_end, minutes=self.config.bar_minutes)
        return _bars_to_minute_ohlc(bars, start_m, end_m)

    def _fetch_baseline_refs(self, ticker, scan_day):
        """Walk back from the scan day to the nearest trading day with 3:50–3:55 PM
        data. Returns (baseline_date, {ref_minute: close_price}) or (None, {})."""
        ref_minutes = self.config.thursday_ref_minutes
        lo, hi = min(ref_minutes), max(ref_minutes)
        for back in range(1, MAX_BASELINE_LOOKBACK + 1):
            day = scan_day - timedelta(days=back)
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

    # ── per-ticker analysis (across all scan days) ───────────────────────────
    def analyze(self, ticker: str) -> dict:
        pcts = [float(p) for p in self.config.ticker_pcts[ticker]]
        ref_minutes = self.config.thursday_ref_minutes
        single_labels = [minute_to_str(m) for m in ref_minutes]
        ref_labels = list(single_labels)
        if self.config.include_avg_baseline:
            ref_labels.append(AVG_LABEL)

        pct_str = ", ".join(f"{p:.2%}" for p in pcts)
        print(f"  Analyzing {ticker} (thresholds ±{pct_str}; "
              f"days: {', '.join(self.config.scan_days)})...", flush=True)

        by_day = {}
        for day_name in self.config.scan_days:
            by_day[day_name] = self._analyze_day(
                ticker, day_name, pcts, ref_labels)

        return {
            "ticker": ticker,
            "pcts": pcts,
            "ref_labels": ref_labels,
            "single_labels": single_labels,
            "days": list(self.config.scan_days),
            "by_day": by_day,
        }

    def _analyze_day(self, ticker, day_name, pcts, ref_labels) -> dict:
        weekday = WEEKDAY_NUM[day_name]
        ref_minutes = self.config.thursday_ref_minutes

        records: list[LevelTouchRecord] = []
        per_session_refs: dict = {}       # {date_str: {single_label: price}} for steadiness
        skipped: list[str] = []
        n_days = 0
        n_baseline_substituted = 0

        for scan_day in get_past_weekday_dates(self.config.backtest_days, weekday):
            ohlc = self._fetch_session(ticker, scan_day)
            if len(ohlc) < MIN_SESSION_BARS:
                skipped.append(f"{scan_day} ({day_name} closed/sparse)")
                time.sleep(0.2)
                continue

            base_date, refs = self._fetch_baseline_refs(ticker, scan_day)
            if not refs:
                skipped.append(f"{scan_day} (no baseline)")
                time.sleep(0.2)
                continue

            sess_high = max(v[0] for v in ohlc.values())
            sess_low = min(v[1] for v in ohlc.values())
            if base_date != prior_trading_weekday(scan_day):
                n_baseline_substituted += 1

            # Build the reference-price map: each single minute + the avg.
            ref_price_by_label = {minute_to_str(m): refs[m] for m in ref_minutes if m in refs}
            per_session_refs[str(scan_day)] = dict(ref_price_by_label)
            if self.config.include_avg_baseline and refs:
                ref_price_by_label[AVG_LABEL] = sum(refs.values()) / len(refs)

            for label in ref_labels:
                R = ref_price_by_label.get(label)
                if R is None:               # this single minute had no bar that week
                    continue
                # Per-day swing is independent of the threshold: the biggest move
                # the scan day made from R in each direction ($ and as a % of R).
                up_swing = sess_high - R
                down_swing = R - sess_low
                up_swing_pct = up_swing / R if R else 0.0
                down_swing_pct = down_swing / R if R else 0.0
                for pct in pcts:
                    up_level = R * (1 + pct)
                    down_level = R * (1 - pct)
                    records.append(LevelTouchRecord(
                        date=str(scan_day), ticker=ticker, day=day_name,
                        ref_label=label, ref_price=round(R, 4), pct=pct,
                        threshold=round(R * pct, 4),
                        up_level=round(up_level, 4), down_level=round(down_level, 4),
                        sess_high=round(sess_high, 4), sess_low=round(sess_low, 4),
                        max_up_swing=round(up_swing, 4),
                        max_down_swing=round(down_swing, 4),
                        max_up_swing_pct=round(up_swing_pct, 6),
                        max_down_swing_pct=round(down_swing_pct, 6),
                        touched_up=bool(sess_high >= up_level),
                        touched_down=bool(sess_low <= down_level),
                    ))
            n_days += 1
            time.sleep(0.2)               # rate-limit courtesy pause

        return {
            "day": day_name,
            "records": records,
            "per_session_refs": per_session_refs,
            "n_days": n_days,
            "n_skipped": len(skipped),
            "skipped_dates": skipped,
            "n_baseline_substituted": n_baseline_substituted,
        }
