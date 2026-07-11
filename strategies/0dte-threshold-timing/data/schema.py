"""
data/schema.py — the minute-data CONTRACT + a thin adapter + a labelled
Black-Scholes SIMULATED fallback.

Contract (long format, one row per contract-minute):
  ts (ET minute-close), symbol, right (call|put), strike, expiry (date),
  bid, ask, underlying.

`bid`/`ask` are TOP-OF-BOOK quotes at the minute close (not last-trade prints).
The Alpaca adapter (data/alpaca_quotes.py) resamples historical option quotes to
the minute close and emits exactly these columns. If a real minute dataset is
provided with a different schema, adapt it here — do NOT change downstream logic.

The simulator is a FALLBACK only, so the pipeline never goes silent when Alpaca
credentials are absent. Its output is tagged SIMULATED and must never be trusted
as an edge — it exists to exercise every code path (regimes, fill modes, folds).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

REQUIRED_COLS = ["ts", "symbol", "right", "strike", "expiry", "bid", "ask", "underlying"]

SOURCE_REAL = "REAL Alpaca option quotes (top-of-book, minute-close)"
SOURCE_SIM = "SIMULATED (Black-Scholes) — NOT A REAL EDGE"


def validate_contract(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Ensure the frame matches the contract; coerce dtypes; drop unusable quotes.
    Rename per cfg column overrides if provided."""
    if cfg is not None:
        rename = {
            cfg.col_ts: "ts", cfg.col_symbol: "symbol", cfg.col_right: "right",
            cfg.col_strike: "strike", cfg.col_expiry: "expiry",
            cfg.col_bid: "bid", cfg.col_ask: "ask", cfg.col_underlying: "underlying",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"data contract missing columns: {missing}")
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df["right"] = df["right"].astype(str).str.lower().map(
        lambda r: "call" if r.startswith("c") else "put")
    df["strike"] = df["strike"].astype(float)
    df["expiry"] = [pd.Timestamp(x).date() for x in df["expiry"]]
    for c in ("bid", "ask", "underlying"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Skip contracts with no valid quote (ask <= 0 or NaN bid/ask handled downstream,
    # but drop the clearly-unusable ask<=0 rows now).
    df = df[(df["ask"] > 0) & df["bid"].notna() & df["ask"].notna()]
    return df.reset_index(drop=True)


# ── Black-Scholes fallback ───────────────────────────────────────────────────
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S, K, tau, sigma, r, right):
    if tau <= 0 or sigma <= 0:
        return max(S - K, 0.0) if right == "call" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * tau) / (sigma * math.sqrt(tau))
    d2 = d1 - sigma * math.sqrt(tau)
    if right == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * tau) * _norm_cdf(d2)
    return K * math.exp(-r * tau) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _listed_expiry(symbol: str, d: date, cfg) -> date:
    """Which expiry this symbol lists as its nearest target on date `d`
    (mirrors the July-2026 cadence for the SIMULATED fallback only)."""
    wd = d.weekday()  # Mon=0
    if symbol in cfg.daily_0dte_names:
        return d
    if symbol in cfg.mon_wed_fri_names:
        for add in range(0, 7):
            e = d + timedelta(days=add)
            if e.weekday() in (0, 2, 4):  # Mon/Wed/Fri
                return e
    # Friday weeklies (ORCL/AMD) and default
    for add in range(0, 7):
        e = d + timedelta(days=add)
        if e.weekday() == 4:
            return e
    return d


def simulate_quote_frame(cfg, n_weeks: int = 10, band: int = 2, seed: int = 7,
                         bar_step: int = 5) -> pd.DataFrame:
    """Generate a labelled SIMULATED contract-minute frame covering the universe
    with the correct per-symbol expiry cadence. Light by construction (5-min bars,
    ATM±`band` strikes) so it runs anywhere; NOT a real edge."""
    rng = np.random.default_rng(seed)
    start = date(2026, 1, 5)  # a Monday
    # consecutive weekdays
    sessions = []
    d = start
    while len(sessions) < n_weeks * 5:
        if d.weekday() < 5:
            sessions.append(d)
        d += timedelta(days=1)

    base_price = {"AAPL": 220, "MSFT": 460, "NVDA": 130, "GOOGL": 185, "AMZN": 200,
                  "META": 560, "TSLA": 250, "ORCL": 210, "AMD": 165}
    rows = []
    minutes = list(range(9 * 60 + 30, 16 * 60 + 1, bar_step))  # 09:30..16:00
    r = cfg.risk_free_rate
    for sym in cfg.tickers:
        S0 = base_price.get(sym, 200)
        sigma = 0.55  # annualized; high so 0DTE % moves are lively
        for d in sessions:
            expiry = _listed_expiry(sym, d, cfg)
            # underlying GBM intraday path (5-min steps)
            n = len(minutes)
            dt = bar_step / (252 * 390)
            shocks = rng.normal(0, 1, n)
            logret = (r - 0.5 * sigma ** 2) * dt + sigma * math.sqrt(dt) * shocks
            under = S0 * np.exp(np.cumsum(logret))
            S0 = float(under[-1])  # carry overnight
            # strike grid around the day-open underlying, $ step ~ 1% of price
            step = max(round(under[0] * 0.01), 1)
            atm = round(under[0] / step) * step
            strikes = [atm + k * step for k in range(-band, band + 1)]
            exp_close = datetime.combine(expiry, datetime.min.time()) + timedelta(hours=16)
            for right in ("call", "put"):
                for K in strikes:
                    if K <= 0:
                        continue
                    for i, mod in enumerate(minutes):
                        now = datetime.combine(d, datetime.min.time()) + timedelta(minutes=mod)
                        tau = max((exp_close - now).total_seconds() / (365 * 24 * 3600), 1e-6)
                        px = bs_price(float(under[i]), float(K), tau, sigma, r, right)
                        px = max(px, 0.05)
                        # Proportional half-spread (multiplicative) so the
                        # market ≤ mid invariant holds exactly on the fallback.
                        half = px * 0.02
                        ts = datetime.combine(d, datetime.min.time()) + timedelta(minutes=mod)
                        rows.append((ts, sym, right, float(K), expiry,
                                     round(px - half, 4), round(px + half, 4),
                                     round(float(under[i]), 2)))
    df = pd.DataFrame(rows, columns=REQUIRED_COLS)
    return df
