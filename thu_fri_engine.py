#!/usr/bin/env python3
"""
Shared engine for the THURSDAY → FRIDAY call-option probability backtest.

Strategy modelled
-----------------
  • The weekly expiry is FRIDAY. You buy the ATM call the trading day BEFORE
    expiry — normally THURSDAY — between 3:55 and 3:59 PM ET (minute by minute).
  • When that Friday is a market holiday (e.g. Good Friday), the option expires
    THURSDAY instead, so the entry rolls back to WEDNESDAY. No week is skipped
    and the data stays REAL (no simulated phantom-Friday):
        normal week    →  buy Thursday,  expiry Friday
        Friday closed  →  buy Wednesday, expiry Thursday
  • You then watch that exact contract all day on the EXPIRY day
    (9:30 AM – 4:00 PM ET).
  • The question: what fraction of the time did the option's expiry-day session
    HIGH reach a target return multiple of your entry price?

Targets are RETURN multiples (profit ÷ premium paid):
      target_price = entry_price × (1 + multiple)
  so for a $0.50 entry:
      1.0x return → ×2.00 → $1.00      (double — your money back + 100%)
      1.5x return → ×2.50 → $1.25
      2.0x return → ×3.00 → $1.50
      2.5x return → ×3.50 → $1.75
"reaching" = the expiry-day intraday HIGH touches the target at ANY point.

Data
----
Real Alpaca option bars when available; Black-Scholes reconstruction (from the
underlying's path + realized vol) as a fallback. Both legs of a sample (the
entry-day price and the expiry-day path) always come from the SAME source, so the
return ratio is never real-vs-simulated apples-to-oranges.

The entry scripts (e.g. backtest_thu_fri_calls.py) just set the knobs at the
top — LOOKBACK_DAYS and RETURN_MULTIPLES — and call run().
"""

import contextlib
import csv
import io
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime

# Load .env if present (Alpaca credentials)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd

from config import Config
from models import SOURCE_REAL, SOURCE_SIM
from utils.date_utils import (
    ET, get_past_weekly_pairs, entry_window_start_utc,
    window_end_utc, session_start_utc, detect_strike_interval,
    get_strike_at_or_above, format_contract_symbol, minute_to_str, is_trading_day,
)
from utils.math_utils import black_scholes_call, realized_vol

# 1 option contract controls 100 shares.
CONTRACT_MULTIPLIER = 100

# Entry-day minutes (minute-of-day): 3:55–3:59 PM ET, one row each.
ENTRY_MINUTES = [955, 956, 957, 958, 959]
ENTRY_TOL = 2              # accept a bar within this many minutes of the target
MIN_SAMPLES = 3           # need >= this many dated samples to report a cell
RESULTS_DIR = "thu_fri_results"

# Expiry-day session bounds (minute-of-day): 9:30 AM → 4:00 PM ET.
SESSION_OPEN_MIN = 9 * 60 + 30
SESSION_CLOSE_MIN = 16 * 60


# ── tiny ANSI helpers (no-op when output is piped to a file) ──────────────
def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def green(t):  return _c(t, "32")
def red(t):    return _c(t, "31")
def yellow(t): return _c(t, "33")
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "36")


def get_fetcher():
    """Alpaca if keys present, else yfinance fallback."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher
    if ALPACA_AVAILABLE:
        f = AlpacaFetcher.from_env()
        if f is not None:
            return f, "Alpaca Markets API"
    return YFinanceFetcher(), "yfinance (set ALPACA_API_KEY for real option data)"


# ── time-to-expiry in TRADING hours (overnight/holidays don't decay) ──────
def trading_hours_until_expiry_close(ts_et: datetime, expiry: date) -> float:
    """Regular-trading-hours (9:30–16:00 ET) remaining from ts_et to expiry close.

    Counts the remainder of the bar's own session plus a full 6.5-hour session
    for each trading day up to and including the expiry day — so the overnight
    gap and any intervening holiday (e.g. a closed Thursday) don't decay time.
    """
    from datetime import timedelta
    close = datetime(expiry.year, expiry.month, expiry.day, 16, 0, tzinfo=ET)
    if ts_et >= close:
        return 0.0
    day = ts_et.date()
    day_open = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)
    day_close = datetime(day.year, day.month, day.day, 16, 0, tzinfo=ET)
    bar = min(max(ts_et, day_open), day_close)
    hours = max((day_close - bar).total_seconds(), 0.0) / 3600.0
    # Full sessions for each trading day after the bar's day, through expiry.
    d = day + timedelta(days=1)
    while d <= expiry:
        if is_trading_day(d):
            hours += 6.5
        d += timedelta(days=1)
    return hours


def _T_years(ts_et: datetime, expiry: date) -> float:
    """Convert remaining trading hours into fractional trading years (floored)."""
    h = trading_hours_until_expiry_close(ts_et, expiry)
    T = h / (252.0 * 6.5)
    return max(T, 1.0 / (252.0 * 6.5 * 60.0))   # floor ~1 trading minute


# ── bar → per-minute extraction ───────────────────────────────────────────
def _bars_minute_field(bars: pd.DataFrame, on_day: date, field: str,
                       lo: int, hi: int) -> dict[int, float]:
    """{minute_of_day: bar[field]} for bars on `on_day` within [lo, hi] minutes ET."""
    out = {}
    if bars is None or bars.empty:
        return out
    for ts, row in bars.iterrows():
        et = pd.Timestamp(ts).tz_convert(ET)
        if et.date() != on_day:
            continue
        m = et.hour * 60 + et.minute
        if lo <= m <= hi:
            out[m] = float(row[field])
    return out


def _price_at(minute_prices: dict[int, float], target_m: int, tol: int):
    """Exact price at target_m, else nearest bar within `tol` minutes."""
    if target_m in minute_prices:
        return minute_prices[target_m]
    cands = [m for m in minute_prices if abs(m - target_m) <= tol]
    if not cands:
        return None
    return minute_prices[min(cands, key=lambda x: abs(x - target_m))]


# ── one (entry-day → expiry-day, ticker) sample ───────────────────────────
def _build_sample(fetcher, ticker, entry_d, expiry_d, strikes, r, sigma):
    """Return a sample dict or None. Tries REAL bars first, then BS simulation.

    Sample = {entry_date, expiry_date, ticker, strike, contract, source,
              exp_high, entries: {minute: entry_price}}
    Both legs share one source so the return ratio stays internally consistent.
    """
    e_start = entry_window_start_utc(entry_d)    # entry day 3:50 PM ET
    e_end = window_end_utc(entry_d)              # entry day 4:00 PM ET
    x_start = session_start_utc(expiry_d)        # expiry day 9:30 AM ET
    x_end = window_end_utc(expiry_d)             # expiry day 4:00 PM ET

    # ---- attempt 1: REAL option bars (try each candidate strike) ----
    for strike in strikes:
        contract = format_contract_symbol(ticker, expiry_d, strike)
        e_opt = fetcher.fetch_historical_option_bars(contract, e_start, e_end)
        x_opt = fetcher.fetch_historical_option_bars(contract, x_start, x_end)

        e_close = _bars_minute_field(e_opt, entry_d, "close", 950, 959)
        x_high_map = _bars_minute_field(x_opt, expiry_d, "high",
                                        SESSION_OPEN_MIN, SESSION_CLOSE_MIN)

        entries = {}
        for m in ENTRY_MINUTES:
            ep = _price_at(e_close, m, ENTRY_TOL)
            if ep is not None and ep > 0:
                entries[m] = ep
        if entries and x_high_map:
            return {
                "entry_date": entry_d, "expiry_date": expiry_d, "ticker": ticker,
                "strike": strike, "contract": contract, "source": SOURCE_REAL,
                "exp_high": max(x_high_map.values()),
                "entries": entries,
            }

    # ---- attempt 2: Black-Scholes simulation (nearest strike) ----
    strike = strikes[0]
    contract = format_contract_symbol(ticker, expiry_d, strike)
    e_stock = fetcher.fetch_historical_stock_bars(ticker, e_start, e_end, minutes=1)
    if e_stock is None or e_stock.empty:
        e_stock = fetcher.fetch_historical_stock_bars(ticker, e_start, e_end, minutes=5)
    x_stock = fetcher.fetch_historical_stock_bars(ticker, x_start, x_end, minutes=1)
    if x_stock is None or x_stock.empty:
        x_stock = fetcher.fetch_historical_stock_bars(ticker, x_start, x_end, minutes=5)
    if e_stock is None or e_stock.empty or x_stock is None or x_stock.empty:
        return None

    # Entry-day prices: BS on the underlying close at each entry minute.
    e_sclose = _bars_minute_field(e_stock, entry_d, "close", 950, 959)
    entry_opt = {}
    for m, spot in e_sclose.items():
        et = datetime(entry_d.year, entry_d.month, entry_d.day, m // 60, m % 60, tzinfo=ET)
        T = _T_years(et, expiry_d)
        px, *_ = black_scholes_call(spot, strike, T, r, sigma)
        if px > 0:
            entry_opt[m] = px
    entries = {}
    for m in ENTRY_MINUTES:
        ep = _price_at(entry_opt, m, ENTRY_TOL)
        if ep is not None and ep > 0:
            entries[m] = ep
    if not entries:
        return None

    # Expiry-day high: BS on each bar's HIGH spot (captures the intraday touch).
    x_shigh = _bars_minute_field(x_stock, expiry_d, "high",
                                 SESSION_OPEN_MIN, SESSION_CLOSE_MIN)
    x_opt_prices = []
    for m, spot in x_shigh.items():
        et = datetime(expiry_d.year, expiry_d.month, expiry_d.day, m // 60, m % 60, tzinfo=ET)
        T = _T_years(et, expiry_d)
        px, *_ = black_scholes_call(spot, strike, T, r, sigma)
        x_opt_prices.append(px)
    if not x_opt_prices:
        return None

    return {
        "entry_date": entry_d, "expiry_date": expiry_d, "ticker": ticker,
        "strike": strike, "contract": contract, "source": SOURCE_SIM,
        "exp_high": max(x_opt_prices),
        "entries": entries,
    }


def collect_samples(fetcher, config, pairs):
    """Gather one sample per (ticker, entry→expiry) pair. {ticker: [samples]}."""
    by_ticker = defaultdict(list)
    for ticker in config.tickers:
        print(f"  Collecting {ticker}...", flush=True)
        # Realized vol for any BS simulation on this ticker.
        closes = []
        if hasattr(fetcher, "get_daily_closes"):
            closes = fetcher.get_daily_closes(ticker, days=40)
        sigma = realized_vol(closes) if len(closes) >= 10 else 0.35
        sigma = max(0.10, min(2.0, sigma))

        for entry_d, expiry_d in pairs:
            # Pick ATM strike from the entry day's late-afternoon spot.
            e_start = entry_window_start_utc(entry_d)
            e_end = window_end_utc(entry_d)
            stock = fetcher.fetch_historical_stock_bars(ticker, e_start, e_end, minutes=1)
            if stock is None or stock.empty:
                stock = fetcher.fetch_historical_stock_bars(ticker, e_start, e_end, minutes=5)
            if stock is None or stock.empty:
                continue
            spot = float(stock["close"].iloc[-1])     # ~3:59 PM entry-day spot
            interval = detect_strike_interval(spot)
            # Buy the strike AT or ABOVE spot (ATM if exact, else first OTM call).
            # Never below. The second entry is only a data-availability fallback
            # (still above spot) for the rare week the exact strike has no bars.
            base = get_strike_at_or_above(spot, interval)
            strikes = [base, round(base + interval, 2)]

            sample = _build_sample(fetcher, ticker, entry_d, expiry_d, strikes,
                                   config.risk_free_rate, sigma)
            if sample is not None:
                sample["spot"] = spot
                by_ticker[ticker].append(sample)
            time.sleep(0.2)   # rate-limit courtesy pause
    return by_ticker


# ── stats ──────────────────────────────────────────────────────────────────
def minute_stats(samples, minute, multiples):
    """Touch-probability stats for one entry minute over a list of samples.

    Returns None if too few samples, else {n, avg_entry, probs:{m: p}, ...}.
    """
    rows = [(s["entries"][minute], s["exp_high"])
            for s in samples if minute in s["entries"]]
    if len(rows) < MIN_SAMPLES:
        return None
    n = len(rows)
    probs = {}
    for m in multiples:
        hits = sum(1 for ep, fh in rows if fh >= ep * (1.0 + m))
        probs[m] = hits / n
    ratios = [fh / ep for ep, fh in rows]
    return {
        "minute": minute, "n": n,
        "avg_entry": sum(ep for ep, _ in rows) / n,
        "avg_max_ratio": sum(ratios) / n,
        "best_ratio": max(ratios),
        "probs": probs,
    }


# ── printing ─────────────────────────────────────────────────────────────
def _legend(multiples):
    parts = [f"{m:g}x→×{1.0 + m:.2f}" for m in multiples]
    return "RETURN targets (price multiple): " + "  ".join(parts)


def _print_ticker_block(ticker, samples, multiples):
    print(bold("=" * 84))
    print(bold(f"  {ticker}"))
    print(bold("=" * 84))
    if not samples:
        print(red("  No usable entry→expiry samples for this ticker.\n"))
        return
    n_real = sum(1 for s in samples if s["source"] == SOURCE_REAL)
    n_sim = len(samples) - n_real
    src = (green("REAL option bars") if n_sim == 0
           else yellow("SIMULATED (Black-Scholes)") if n_real == 0
           else yellow(f"MIXED ({n_real} real / {n_sim} sim)"))
    print(f"  Data source : {src}   |   {len(samples)} Thu→Fri pairs collected")
    print(f"  {_legend(multiples)}")
    print()

    head = f"  {'Entry':>6} {'N':>4} {'AvgEntry':>9} {'AvgMax':>7} {'BestMax':>8} "
    for m in multiples:
        head += f"{('P>=' + format(m, 'g') + 'x'):>9}"
    print(head)
    rule = f"  {'-'*6} {'-'*4} {'-'*9} {'-'*7} {'-'*8} " + " ".join('-'*8 for _ in multiples)
    print(rule)

    for minute in ENTRY_MINUTES:
        st = minute_stats(samples, minute, multiples)
        label = minute_to_str(minute).replace(" PM", "")
        if st is None:
            print(f"  {label:>6} {yellow('(insufficient samples)')}")
            continue
        row = (f"  {label:>6} {st['n']:>4} ${st['avg_entry']:>7.2f} "
               f"{st['avg_max_ratio']:>6.2f}x {st['best_ratio']:>7.2f}x ")
        for m in multiples:
            p = st["probs"][m]
            cell = f"{p:>8.0%}"
            col = green if p >= 0.50 else (yellow if p >= 0.30 else None)
            row += (col(cell) if col else cell) + " "
        print(row)
    print()


def _pool_all(by_ticker):
    pooled = []
    for samples in by_ticker.values():
        pooled.extend(samples)
    return pooled


def _print_all(by_ticker, config, multiples):
    for ticker in config.tickers:
        _print_ticker_block(ticker, by_ticker.get(ticker, []), multiples)
    pooled = _pool_all(by_ticker)
    print(bold("=" * 84))
    print(bold("  ALL TICKERS COMBINED"))
    print(bold("=" * 84))
    if not pooled:
        print(red("  No samples collected across any ticker.\n"))
        return
    print(f"  {_legend(multiples)}\n")
    head = f"  {'Entry':>6} {'N':>4} {'AvgEntry':>9} {'AvgMax':>7} {'BestMax':>8} "
    for m in multiples:
        head += f"{('P>=' + format(m, 'g') + 'x'):>9}"
    print(head)
    print(f"  {'-'*6} {'-'*4} {'-'*9} {'-'*7} {'-'*8} "
          + " ".join('-'*8 for _ in multiples))
    for minute in ENTRY_MINUTES:
        st = minute_stats(pooled, minute, multiples)
        label = minute_to_str(minute).replace(" PM", "")
        if st is None:
            print(f"  {label:>6} {yellow('(insufficient samples)')}")
            continue
        row = (f"  {label:>6} {st['n']:>4} ${st['avg_entry']:>7.2f} "
               f"{st['avg_max_ratio']:>6.2f}x {st['best_ratio']:>7.2f}x ")
        for m in multiples:
            p = st["probs"][m]
            cell = f"{p:>8.0%}"
            col = green if p >= 0.50 else (yellow if p >= 0.30 else None)
            row += (col(cell) if col else cell) + " "
        print(row)
    print()


# ── CSV ──────────────────────────────────────────────────────────────────
def _save_csv(path, method_label, lookback_days, source_label, multiples,
              by_ticker, config):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# {method_label}"])
        w.writerow([f"# Lookback = {lookback_days} calendar days"])
        w.writerow([f"# Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  "
                    f"data source: {source_label}"])
        w.writerow([f"# Targets are RETURN multiples: target_price = entry x (1 + m)"])
        w.writerow([f"# multiples = {', '.join(format(m, 'g') for m in multiples)}"])
        w.writerow([])

        # ---- DETAIL: one row per (pair, entry minute) ----
        w.writerow(["DETAIL — one row per entry-day entry"])
        w.writerow(["ticker", "entry_day", "entry_weekday", "expiry_day",
                    "expiry_weekday", "strike", "contract", "source",
                    "entry_time", "entry_price", "expiry_high", "max_return_multiple"]
                   + [f"hit_{m:g}x" for m in multiples])
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for ticker in config.tickers:
            for s in by_ticker.get(ticker, []):
                for minute in ENTRY_MINUTES:
                    ep = s["entries"].get(minute)
                    if ep is None:
                        continue
                    fh = s["exp_high"]
                    max_ret = (fh / ep) - 1.0
                    src = "REAL" if s["source"] == SOURCE_REAL else "SIM"
                    w.writerow([ticker, s["entry_date"], wd[s["entry_date"].weekday()],
                                s["expiry_date"], wd[s["expiry_date"].weekday()],
                                s["strike"], s["contract"], src, minute_to_str(minute),
                                round(ep, 4), round(fh, 4), round(max_ret, 4)]
                               + [int(fh >= ep * (1.0 + m)) for m in multiples])
        w.writerow([])

        # ---- SUMMARY: probabilities per ticker × entry minute ----
        w.writerow(["SUMMARY — touch probability by ticker and entry minute"])
        w.writerow(["ticker", "entry_time", "n_samples", "avg_entry_price",
                    "avg_max_ratio", "best_max_ratio"]
                   + [f"prob_{m:g}x" for m in multiples])
        scopes = [(t, by_ticker.get(t, [])) for t in config.tickers]
        scopes.append(("ALL", _pool_all(by_ticker)))
        for name, samples in scopes:
            for minute in ENTRY_MINUTES:
                st = minute_stats(samples, minute, multiples)
                if st is None:
                    w.writerow([name, minute_to_str(minute), 0, "", "", ""]
                               + ["" for _ in multiples])
                    continue
                w.writerow([name, minute_to_str(minute), st["n"],
                            round(st["avg_entry"], 4), round(st["avg_max_ratio"], 4),
                            round(st["best_ratio"], 4)]
                           + [f"{st['probs'][m]:.4f}" for m in multiples])


# ── driver ───────────────────────────────────────────────────────────────
def run(lookback_days, multiples, method_label="THURSDAY → FRIDAY call probability"):
    config = Config()
    config.backtest_days = lookback_days

    print(bold("\n" + "═" * 84))
    print(bold(f"  {method_label}"))
    print(bold(f"  Lookback window: {lookback_days} calendar days"))
    print(bold("═" * 84))

    fetcher, source_label = get_fetcher()
    pairs = get_past_weekly_pairs(lookback_days)
    shifted = sum(1 for e, x in pairs if x.weekday() != 4)
    print(f"  Data source : {source_label}")
    print(f"  Tickers     : {', '.join(config.tickers)}")
    print(f"  Weekly pairs in window  : {len(pairs)}  "
          f"(normal Thu→Fri; {shifted} shifted to Wed→Thu for a closed Friday)")
    print(f"  Entry minutes (entry day): "
          f"{', '.join(minute_to_str(m) for m in ENTRY_MINUTES)}")
    print(f"  {_legend(multiples)}\n")

    by_ticker = collect_samples(fetcher, config, pairs)

    print()
    _print_all(by_ticker, config, multiples)

    # Plain-text capture (no ANSI) for the .txt file.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _print_all(by_ticker, config, multiples)
    txt_body = buf.getvalue()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base = f"thu_fri_calls_{lookback_days}days_{stamp}"
    csv_path = os.path.join(RESULTS_DIR, f"{base}.csv")
    txt_path = os.path.join(RESULTS_DIR, f"{base}.txt")

    _save_csv(csv_path, method_label, lookback_days, source_label, multiples,
              by_ticker, config)

    hdr = (f"{method_label}\n"
           f"Lookback = {lookback_days} calendar days\n"
           f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}  |  {source_label}\n"
           f"Targets: target_price = entry x (1 + m); "
           f"m in {', '.join(format(m, 'g') for m in multiples)}\n"
           + "=" * 84 + "\n\n")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(hdr)
        f.write(txt_body)

    print(bold("─" * 84))
    print(f"  {cyan('Saved CSV:')} {bold(csv_path)}")
    print(f"  {cyan('Saved TXT:')} {bold(txt_path)}")
    print(f"  CSV: per-entry detail + probability summary.  TXT: full tables.")
    print(bold("─" * 84))
    print()
