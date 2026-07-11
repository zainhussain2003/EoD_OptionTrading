"""
data/alpaca_quotes.py — Alpaca historical OPTION-QUOTES adapter → data contract.

The repo's existing fetcher pulls option OHLCV *bars* (last-trade prints). This
study needs TOP-OF-BOOK bid/ask at each minute close, so this adapter uses the
historical option QUOTES endpoint and resamples to the minute close (the last
quote at/before each minute boundary), then emits the long contract:

  ts, symbol, right, strike, expiry, bid, ask, underlying

Contract discovery is EMPIRICAL: we list the option contracts Alpaca actually
has for each underlying over the window (the vendor is the source of truth for
which expiries exist), keep ATM ± cfg.strike_band strikes per expiry, and only
pull the sessions where that expiry is the nearest forward target (which is all
the analysis uses) to keep the quote volume sane.

Everything is wrapped so a failure returns None and the caller falls back to the
labelled SIMULATED frame — the pipeline never goes silent. This module is written
to the documented alpaca-py interface; the self-hosted runner (with your keys and
data subscription) is where it executes against the live API.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

try:
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, OptionQuotesRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOptionContractsRequest
    from alpaca.trading.enums import AssetStatus, ContractType
    ALPACA_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    ALPACA_AVAILABLE = False


def _keys():
    api = os.getenv("ALPACA_API_KEY", "")
    sec = os.getenv("ALPACA_SECRET_KEY", "") or os.getenv("ALPACA_API_SECRET", "")
    return api, sec


def credentials_present() -> bool:
    api, sec = _keys()
    return bool(api and sec and ALPACA_AVAILABLE)


class AlpacaQuotesAdapter:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        self.log = log
        api, sec = _keys()
        self.stock = StockHistoricalDataClient(api, sec)
        self.option = OptionHistoricalDataClient(api, sec)
        self.trading = TradingClient(api, sec, paper=cfg.alpaca_paper)

    # ── contract discovery (empirical expiry source of truth) ────────────────
    def list_contracts(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Return DataFrame[contract_symbol, strike, expiry, right] Alpaca lists
        for `symbol` with expiries in [start, end]."""
        recs = []
        page_token = None
        while True:
            req = GetOptionContractsRequest(
                underlying_symbols=[symbol],
                status=AssetStatus.ACTIVE,
                expiration_date_gte=start,
                expiration_date_lte=end,
                limit=10000,
                page_token=page_token,
            )
            resp = self.trading.get_option_contracts(req)
            contracts = getattr(resp, "option_contracts", resp)
            for c in contracts:
                recs.append({
                    "contract_symbol": c.symbol,
                    "strike": float(c.strike_price),
                    "expiry": c.expiration_date if isinstance(c.expiration_date, date)
                    else pd.Timestamp(c.expiration_date).date(),
                    "right": "call" if str(c.type).lower().endswith("call") else "put",
                })
            page_token = getattr(resp, "next_page_token", None)
            if not page_token:
                break
        return pd.DataFrame(recs)

    # ── underlying minute closes ─────────────────────────────────────────────
    def underlying_minutes(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame(1, TimeFrameUnit.Minute),
            start=start, end=end, adjustment="raw", feed="iex",
        )
        bars = self.stock.get_stock_bars(req).df
        if bars is None or bars.empty:
            return pd.DataFrame()
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(symbol, level="symbol")
        bars.index = pd.to_datetime(bars.index, utc=True)
        return bars[["close"]].rename(columns={"close": "underlying"})

    # ── option quotes → minute close top-of-book ─────────────────────────────
    def option_minute_quotes(self, contract_symbol: str,
                             start: datetime, end: datetime) -> pd.DataFrame:
        req = OptionQuotesRequest(
            symbol_or_symbols=contract_symbol, start=start, end=end,
            feed=self.cfg.option_feed,
        )
        q = self.option.get_option_quotes(req).df
        if q is None or q.empty:
            return pd.DataFrame()
        if isinstance(q.index, pd.MultiIndex):
            q = q.xs(contract_symbol, level="symbol")
        q.index = pd.to_datetime(q.index, utc=True)
        q = q[["bid_price", "ask_price"]].rename(
            columns={"bid_price": "bid", "ask_price": "ask"})
        # last quote at/before each minute close (top-of-book at the minute).
        minute = q.resample("1min", label="right", closed="right").last()
        return minute.dropna(how="all")

    # ── orchestration ────────────────────────────────────────────────────────
    def fetch_universe(self) -> pd.DataFrame:
        cfg = self.cfg
        end_d = datetime.now(ET).date()
        start_d = end_d - timedelta(days=cfg.lookback_days)
        all_rows = []
        for sym in cfg.tickers:
            try:
                cdf = self.list_contracts(sym, start_d, end_d + timedelta(days=7))
            except Exception as e:
                self.log(f"  [alpaca] {sym}: contract listing failed: {type(e).__name__}: {e}")
                continue
            if cdf.empty:
                self.log(f"  [alpaca] {sym}: no contracts listed")
                continue
            expiries = sorted(cdf["expiry"].unique())
            sym_rows = self._fetch_symbol(sym, cdf, expiries, start_d, end_d)
            if sym_rows is not None and not sym_rows.empty:
                all_rows.append(sym_rows)
                self.log(f"  [alpaca] {sym}: {len(sym_rows)} contract-minutes")
        if not all_rows:
            return pd.DataFrame()
        return pd.concat(all_rows, ignore_index=True)

    def _fetch_symbol(self, sym, cdf, expiries, start_d, end_d) -> pd.DataFrame:
        """For each session, pick the nearest-forward target expiry, keep ATM±band
        strikes, pull minute quotes, and join the underlying."""
        cfg = self.cfg
        rows = []
        # business-day sessions in the window
        sessions = pd.bdate_range(start_d, end_d).date
        for d in sessions:
            forward = [e for e in expiries if e >= d]
            if not forward:
                continue
            tgt = forward[0]
            win_start = datetime.combine(d, datetime.min.time(), tzinfo=ET).astimezone(UTC)
            win_end = datetime.combine(d, datetime.min.time(), tzinfo=ET).astimezone(UTC) + timedelta(hours=16)
            und = self.underlying_minutes(sym, win_start, win_end)
            if und.empty:
                continue
            u_open = float(und["underlying"].iloc[0])
            day_contracts = cdf[cdf["expiry"] == tgt]
            for right in ("call", "put"):
                rc = day_contracts[day_contracts["right"] == right].copy()
                if rc.empty:
                    continue
                rc["dist"] = (rc["strike"] - u_open).abs()
                keep = rc.sort_values("dist").head(2 * cfg.strike_band + 1)
                for _, c in keep.iterrows():
                    mq = self.option_minute_quotes(c["contract_symbol"], win_start, win_end)
                    if mq.empty:
                        continue
                    joined = mq.join(und, how="inner")
                    joined = joined.dropna(subset=["bid", "ask", "underlying"])
                    if joined.empty:
                        continue
                    ts_et = joined.index.tz_convert(ET).tz_localize(None)
                    rows.append(pd.DataFrame({
                        "ts": ts_et, "symbol": sym, "right": right,
                        "strike": float(c["strike"]), "expiry": tgt,
                        "bid": joined["bid"].to_numpy(), "ask": joined["ask"].to_numpy(),
                        "underlying": joined["underlying"].to_numpy(),
                    }))
        if not rows:
            return pd.DataFrame()
        return pd.concat(rows, ignore_index=True)


def fetch_universe(cfg, log=print) -> pd.DataFrame:
    """Top-level entry: returns a contract-shaped frame, or empty on any failure."""
    if not credentials_present():
        log("  [alpaca] credentials/library unavailable — cannot fetch real quotes")
        return pd.DataFrame()
    try:
        return AlpacaQuotesAdapter(cfg, log=log).fetch_universe()
    except Exception as e:  # pragma: no cover - defensive
        log(f"  [alpaca] fetch_universe failed: {type(e).__name__}: {e}")
        return pd.DataFrame()
