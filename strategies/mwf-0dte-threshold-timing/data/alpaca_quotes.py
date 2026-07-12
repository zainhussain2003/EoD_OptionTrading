"""
data/alpaca_quotes.py — Alpaca historical OPTION adapter → data contract.

Mirrors the PROVEN key/client structure used by calls/ and puts/ (which pull real
data on the runner):
  - `load_dotenv()` then read ALPACA_API_KEY + ALPACA_API_SECRET from env
    (ALPACA_SECRET_KEY is accepted too, since the pipeline sets that name);
  - the import block is confined to the `alpaca.data.*` layer those fetchers use
    — no `alpaca.trading.*` — so the module always loads on the runner;
  - contracts are addressed by CONSTRUCTED OCC symbols (format_contract_symbol),
    the same pattern calls/ and puts/ use, which works for EXPIRED contracts (a
    12-month history is almost all expired — listing "active" contracts misses it).

This study needs TOP-OF-BOOK bid/ask at the minute close, so the PRIMARY path is
historical option QUOTES (get_option_quotes), resampled to the minute close. The
quotes request is imported behind a SEPARATE guard; if a runner's alpaca-py lacks
it, we fall back to option BARS (last-trade close) with a modeled spread — clearly
labelled so it is never mistaken for true top-of-book. Only if neither works does
strategy.py drop to the labelled SIMULATED frame. Every fallback logs its reason.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

try:  # match calls/puts: load a local .env if present
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# ── proven import block (same layer calls/puts use) ──────────────────────────
_IMPORT_ERROR = ""
try:
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, OptionBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_AVAILABLE = True
except Exception as e:  # pragma: no cover - import guard
    ALPACA_AVAILABLE = False
    _IMPORT_ERROR = f"{type(e).__name__}: {e}"

# ── option QUOTES request: separate guard so its absence can't break loading ─
try:
    from alpaca.data.requests import OptionQuotesRequest
    HAVE_QUOTES = True
except Exception:
    HAVE_QUOTES = False

SOURCE_REAL_QUOTES = "REAL Alpaca option quotes (top-of-book, minute-close)"
SOURCE_REAL_BARS = "REAL Alpaca option bars (last-trade close) + modeled spread"


# ── OCC symbol + strike helpers (mirror repo conventions, self-contained) ────
def format_contract_symbol(ticker: str, expiry: date, strike: float, right: str) -> str:
    """OCC symbol, e.g. AAPL260612C00212500."""
    cp = "C" if right.lower().startswith("c") else "P"
    return f"{ticker}{expiry.strftime('%y%m%d')}{cp}{round(strike * 1000):08d}"


def strike_interval(spot: float) -> float:
    if spot >= 500:
        return 5.0
    if spot >= 200:
        return 2.5
    if spot >= 100:
        return 5.0
    if spot >= 50:
        return 2.5
    return 1.0


def atm_and_band_strikes(spot: float, band: int) -> list:
    step = strike_interval(spot)
    atm = round(spot / step) * step
    return sorted({round(atm + k * step, 2) for k in range(-band, band + 1) if atm + k * step > 0})


def _keys():
    api = os.getenv("ALPACA_API_KEY", "")
    # calls/puts read ALPACA_API_SECRET; the pipeline env sets ALPACA_SECRET_KEY.
    sec = os.getenv("ALPACA_API_SECRET", "") or os.getenv("ALPACA_SECRET_KEY", "")
    return api, sec


def availability_reason() -> str:
    api, sec = _keys()
    if not ALPACA_AVAILABLE:
        return f"alpaca-py import failed ({_IMPORT_ERROR})"
    if not api or not sec:
        return "ALPACA_API_KEY / ALPACA_API_SECRET not set in env"
    return "ok"


def credentials_present() -> bool:
    return availability_reason() == "ok"


class AlpacaQuotesAdapter:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        self.log = log
        api, sec = _keys()
        # same client construction as calls/puts alpaca_fetcher
        self._stock = StockHistoricalDataClient(api, sec)
        self._option = OptionHistoricalDataClient(api, sec)
        self._last_src = None            # "quotes" | "bars" for the last non-empty fetch
        self.symbol_source = {}          # sym -> "quotes" | "bars" | "mixed" | "none"

    # ── underlying minute closes ─────────────────────────────────────────────
    def underlying_minutes(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame(1, TimeFrameUnit.Minute),
            start=start, end=end, adjustment="raw", feed="iex",
        )
        bars = self._stock.get_stock_bars(req).df
        if bars is None or bars.empty:
            return pd.DataFrame()
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(symbol, level="symbol")
        bars.index = pd.to_datetime(bars.index, utc=True)
        return bars[["close"]].rename(columns={"close": "underlying"})

    # ── option minute bid/ask: quotes primary, bars fallback ─────────────────
    def option_minute_bidask(self, contract_symbol: str,
                             start: datetime, end: datetime) -> pd.DataFrame:
        """Return minute-indexed DataFrame[bid, ask] (UTC index), or empty.
        Sets self._last_src to 'quotes' or 'bars' on a non-empty result."""
        self._last_src = None
        if HAVE_QUOTES:
            df = self._quotes(contract_symbol, start, end)
            if not df.empty:
                self._last_src = "quotes"
                return df
        # fallback: last-trade bars + modeled spread (mirrors calls/puts bars use)
        df = self._bars_bidask(contract_symbol, start, end)
        if not df.empty:
            self._last_src = "bars"
        return df

    def _quotes(self, contract_symbol, start, end) -> pd.DataFrame:
        try:
            req = OptionQuotesRequest(symbol_or_symbols=contract_symbol, start=start,
                                      end=end, feed=self.cfg.option_feed)
            q = self._option.get_option_quotes(req).df
        except Exception:
            return pd.DataFrame()
        if q is None or q.empty:
            return pd.DataFrame()
        if isinstance(q.index, pd.MultiIndex):
            q = q.xs(contract_symbol, level="symbol")
        q.index = pd.to_datetime(q.index, utc=True)
        bidc = "bid_price" if "bid_price" in q.columns else ("bid" if "bid" in q.columns else None)
        askc = "ask_price" if "ask_price" in q.columns else ("ask" if "ask" in q.columns else None)
        if bidc is None or askc is None:
            return pd.DataFrame()
        q = q[[bidc, askc]].rename(columns={bidc: "bid", askc: "ask"})
        minute = q.resample("1min", label="right", closed="right").last()
        return minute.dropna(how="all")

    def _bars_bidask(self, contract_symbol, start, end) -> pd.DataFrame:
        """Last-trade OHLCV bars → synthetic bid/ask via a modeled spread. Flagged."""
        try:
            req = OptionBarsRequest(
                symbol_or_symbols=contract_symbol,
                timeframe=TimeFrame(1, TimeFrameUnit.Minute),
                start=start, end=end, feed=self.cfg.option_feed,
            )
            b = self._option.get_option_bars(req).df
        except Exception:
            return pd.DataFrame()
        if b is None or b.empty:
            return pd.DataFrame()
        if isinstance(b.index, pd.MultiIndex):
            b = b.xs(contract_symbol, level="symbol")
        b.index = pd.to_datetime(b.index, utc=True)
        close = b["close"].astype(float)
        half = np.maximum(close * 0.01, 0.05)  # modeled ~1% half-spread, 5c floor
        return pd.DataFrame({"bid": (close - half).clip(lower=0.0),
                             "ask": close + half}, index=b.index)

    def _session_utc(self, d: date) -> tuple:
        base = datetime.combine(d, datetime.min.time(), tzinfo=ET)
        return base.astimezone(UTC), (base + timedelta(hours=16)).astimezone(UTC)

    def fetch_symbol(self, sym: str, end_d: date) -> pd.DataFrame:
        """0DTE ONLY: for each Mon/Wed/Fri session inside that weekday's lookback,
        probe the SAME-DAY expiry (one probe per session — no forward scan). If it
        has data, pull ATM±band both rights for that same-day expiry. A symbol with
        no same-day Mon/Wed expiry simply yields only its Friday sessions."""
        cfg = self.cfg
        rows = []
        start_d = end_d - timedelta(days=cfg.max_lookback_days)
        sessions = [d.date() for d in pd.bdate_range(start_d, end_d)]
        n_days = 0
        n_quotes = n_bars = 0
        for d in sessions:
            wd = d.weekday()
            if wd not in cfg.expiry_dows:                 # only Mon/Wed/Fri
                continue
            if (end_d - d).days > cfg.lookback_for_dow(wd):  # per-DOW window
                continue
            s_utc, e_utc = self._session_utc(d)
            und = self.underlying_minutes(sym, s_utc, e_utc)
            if und.empty:
                continue
            spot = float(und["underlying"].iloc[0])
            strikes = atm_and_band_strikes(spot, cfg.strike_band)
            atm = min(strikes, key=lambda k: abs(k - spot))
            # single same-day (0DTE) probe: does a contract expiring TODAY exist?
            probe = self.option_minute_bidask(
                format_contract_symbol(sym, d, atm, "call"), s_utc, e_utc)
            if probe.empty:
                continue
            n_days += 1
            for right in ("call", "put"):
                for K in strikes:
                    mq = self.option_minute_bidask(
                        format_contract_symbol(sym, d, K, right), s_utc, e_utc)
                    if mq.empty:
                        continue
                    if self._last_src == "quotes":
                        n_quotes += 1
                    elif self._last_src == "bars":
                        n_bars += 1
                    joined = mq.join(und, how="inner").dropna(subset=["bid", "ask", "underlying"])
                    if joined.empty:
                        continue
                    ts_et = joined.index.tz_convert(ET).tz_localize(None)
                    rows.append(pd.DataFrame({
                        "ts": ts_et, "symbol": sym, "right": right,
                        "strike": float(K), "expiry": d,   # 0DTE: expiry == trade date
                        "bid": joined["bid"].to_numpy(), "ask": joined["ask"].to_numpy(),
                        "underlying": joined["underlying"].to_numpy(),
                    }))
        # per-symbol source label for option (c) reporting
        if n_quotes and n_bars:
            self.symbol_source[sym] = "mixed"
        elif n_quotes:
            self.symbol_source[sym] = "quotes"
        elif n_bars:
            self.symbol_source[sym] = "bars"
        else:
            self.symbol_source[sym] = "none"
        if not rows:
            self.log(f"  [alpaca] {sym}: no 0DTE option data ({len(sessions)} sessions scanned)")
            return pd.DataFrame()
        out = pd.concat(rows, ignore_index=True)
        self.log(f"  [alpaca] {sym}: {len(out):,} contract-minutes over {n_days} 0DTE "
                 f"sessions [source={self.symbol_source[sym]}]")
        return out

    def fetch_universe(self) -> pd.DataFrame:
        cfg = self.cfg
        end_d = datetime.now(ET).date()
        parts = []
        for sym in cfg.tickers:
            try:
                sdf = self.fetch_symbol(sym, end_d)
            except Exception as e:
                self.log(f"  [alpaca] {sym}: fetch failed: {type(e).__name__}: {e}")
                self.symbol_source[sym] = "none"
                continue
            if not sdf.empty:
                parts.append(sdf)
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def fetch_universe(cfg, log=print) -> tuple:
    """Return (contract_df, source_label, per_symbol_source). Empty df + '' + {} on
    failure; the caller then falls back to the labelled SIMULATED frame. Option (c):
    quotes are tried first and bars used per-symbol when quotes are empty."""
    reason = availability_reason()
    if reason != "ok":
        log(f"  [alpaca] cannot fetch real data — {reason}")
        return pd.DataFrame(), "", {}
    try:
        adapter = AlpacaQuotesAdapter(cfg, log=log)
        df = adapter.fetch_universe()
        if df.empty:
            return df, "", adapter.symbol_source
        srcs = set(v for v in adapter.symbol_source.values() if v not in ("none",))
        if srcs == {"quotes"}:
            label = SOURCE_REAL_QUOTES
        elif srcs == {"bars"}:
            label = SOURCE_REAL_BARS
        else:
            label = "REAL Alpaca option data (per-symbol quotes/bars — see run_config)"
        return df, label, adapter.symbol_source
    except Exception as e:  # pragma: no cover - defensive
        log(f"  [alpaca] fetch_universe failed: {type(e).__name__}: {e}")
        return pd.DataFrame(), "", {}
