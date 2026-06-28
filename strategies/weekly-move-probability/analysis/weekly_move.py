"""
Core analysis for the weekly-move-probability study.

For every consecutive pair of Fridays in the lookback window, and for each ticker,
this module measures the TERMINAL (close-to-close) weekly return between the two
Fridays' near-close reference prices and buckets it as up / down / flat.

  1. REFERENCE PRICE — for a given Friday, fetch that day's 1-minute stock bars
     and take the AVERAGE of the CLOSE prices over the 3:50–4:00 PM ET window
     (the ten bars 3:50 … 3:59; the 4:00 bar is excluded). This is the leg's
     reference price R.

       HOLIDAY RULE: if the Friday is a market holiday / closed (no usable
       3:50–4:00 window), step back to the prior Thursday's window (then Wed …)
       and flag the leg as a fallback. Applied to both the entry and exit legs.

  2. PAIR — entry = each Friday's reference, exit = the FOLLOWING Friday's
     reference (one week / 7 calendar days later).

  3. WEEKLY RETURN — (exit_ref / entry_ref) - 1, bucketed:
       up   if return >= +threshold     (default +1.5%)
       down if return <= -threshold     (default -1.5%)
       flat otherwise                   (inside the ±band)

A week is DROPPED (never silently filled) if either leg lacks a usable reference
window even after the holiday step-back; the reason is recorded.

Nothing here trades or prices options — it only measures realized weekly drift.
"""
import time
from datetime import timedelta

import pandas as pd

from config import Config
from models import WeeklyMoveRecord
from utils.date_utils import ET, get_past_friday_dates, window_minute_utc


def _bars_to_minute_close(bars, start_m: int, end_m: int) -> dict:
    """{minute_of_day: close} for bars whose ET minute is inside [start_m, end_m)."""
    out = {}
    if bars is None or bars.empty:
        return out
    for ts, row in bars.iterrows():
        et_ts = pd.Timestamp(ts).tz_convert(ET)
        m = et_ts.hour * 60 + et_ts.minute
        if start_m <= m < end_m:
            out[m] = float(row['close'])
    return out


class WeeklyMoveAnalyzer:
    """Builds the per-week Friday→next-Friday terminal-return records for every
    ticker, applying the 3:50–4:00 PM reference and the Thursday holiday rule."""

    def __init__(self, fetcher, config: Config):
        self.fetcher = fetcher
        self.config = config

    def run(self, tickers=None) -> dict:
        tickers = tickers or list(self.config.tickers)
        return {t: self.analyze(t) for t in tickers}

    # ── reference-price fetch (with holiday step-back) ───────────────────────
    def _fetch_reference(self, ticker, friday):
        """Average of 3:50–4:00 PM ET minute closes for `friday`, stepping back to
        the prior Thursday/Wed… if the Friday is closed.

        Returns (ref_price, ref_date, n_bars, fallback) or (None, None, 0, False).
        """
        start_m = self.config.ref_start_minute
        end_m = self.config.ref_end_minute
        for back in range(0, self.config.max_baseline_lookback + 1):
            day = friday - timedelta(days=back)
            if day.weekday() >= 5:              # skip weekends entirely
                continue
            win_start = window_minute_utc(day, start_m - 2)   # small pad for alignment
            win_end = window_minute_utc(day, end_m + 2)
            bars = self.fetcher.fetch_historical_stock_bars(
                ticker, win_start, win_end, minutes=self.config.bar_minutes)
            closes = _bars_to_minute_close(bars, start_m, end_m)
            if len(closes) >= self.config.min_ref_bars:
                ref = sum(closes.values()) / len(closes)
                return ref, day, len(closes), (day != friday)
            time.sleep(0.1)
        return None, None, 0, False

    # ── per-ticker analysis ──────────────────────────────────────────────────
    def analyze(self, ticker: str) -> dict:
        thr = float(self.config.threshold)
        print(f"  Analyzing {ticker} (±{thr:.2%} band)...", flush=True)

        fridays = get_past_friday_dates(self.config.backtest_days)

        # 1. Build the per-Friday reference map (nominal Friday → leg detail).
        legs: dict = {}
        for friday in fridays:
            ref, ref_date, n_bars, fallback = self._fetch_reference(ticker, friday)
            legs[friday] = {
                "ref": ref, "ref_date": ref_date,
                "n_bars": n_bars, "fallback": fallback,
            }
            time.sleep(0.15)              # rate-limit courtesy pause

        # 2. Pair each Friday with the following Friday (exactly 7 days later).
        records: list[WeeklyMoveRecord] = []
        dropped: list[str] = []
        for i in range(len(fridays) - 1):
            entry_d, exit_d = fridays[i], fridays[i + 1]
            # Consecutive entries from get_past_friday_dates are 7 days apart;
            # guard against any gap so we never measure a 2-week move as 1 week.
            if (exit_d - entry_d).days != 7:
                dropped.append(f"{entry_d}→{exit_d} (not consecutive Fridays)")
                continue
            e, x = legs[entry_d], legs[exit_d]
            if e["ref"] is None and x["ref"] is None:
                dropped.append(f"week of {entry_d} (no entry or exit reference)")
                continue
            if e["ref"] is None:
                dropped.append(f"week of {entry_d} (no entry reference)")
                continue
            if x["ref"] is None:
                dropped.append(f"week of {entry_d} (no exit reference)")
                continue

            weekly_return = (x["ref"] / e["ref"]) - 1.0
            if weekly_return >= thr:
                bucket = "up"
            elif weekly_return <= -thr:
                bucket = "down"
            else:
                bucket = "flat"

            records.append(WeeklyMoveRecord(
                ticker=ticker,
                entry_date=str(entry_d), exit_date=str(exit_d),
                entry_ref=round(e["ref"], 4), exit_ref=round(x["ref"], 4),
                weekly_return=round(weekly_return, 6),
                bucket=bucket, threshold=thr,
                entry_ref_date=str(e["ref_date"]), exit_ref_date=str(x["ref_date"]),
                entry_fallback=bool(e["fallback"]), exit_fallback=bool(x["fallback"]),
                n_entry_bars=e["n_bars"], n_exit_bars=x["n_bars"],
            ))

        n_fallback_weeks = sum(1 for r in records
                               if r.entry_fallback or r.exit_fallback)
        thin = self.config.min_ref_bars_thin
        n_thin_weeks = sum(1 for r in records
                           if r.n_entry_bars < thin or r.n_exit_bars < thin)

        return {
            "ticker": ticker,
            "threshold": thr,
            "records": records,
            "n_weeks": len(records),
            "n_dropped": len(dropped),
            "dropped": dropped,
            "n_fallback_weeks": n_fallback_weeks,
            "n_thin_weeks": n_thin_weeks,
        }
