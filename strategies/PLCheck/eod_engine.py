#!/usr/bin/env python
"""
End-of-day fixed-window P/L engine for TSLA CALLS.

Rule (no optimization, just a straight P/L check):
  - Each eligible day, buy the ATM TSLA call at the ENTRY minute (default 3:45 PM ET)
    and sell it at the EXIT minute (default 3:55 PM ET).
  - Number of contracts = MAX(1, CEILING(budget / (entry_price * 100)))
    (with budget = $100 this keeps each trade's premium spend near $100).
  - P/L per trade = (exit_price - entry_price) * 100 * contracts.

The data-capture layer (analysis/backtester.py) fetches full-day 1-minute option
bars for the ATM TSLA call on every past Friday inside the look-back window — the
days TSLA has 0DTE options. Alpaca is used when ALPACA_API_KEY / ALPACA_SECRET_KEY
are set; otherwise it degrades to a Black-Scholes simulation so the run never goes
silent (provenance is recorded either way).

Metrics produced: win %, total & average P/L, P/L concentration, biggest win,
biggest loss, premium spent and return on spend.
"""
from __future__ import annotations

import math

# Load .env if present (Alpaca credentials)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import Config
from analysis.backtester import Backtester
from models import SOURCE_REAL, SOURCE_NO_STOCK
from utils.date_utils import minute_to_str

# 1 option contract controls 100 shares.
CONTRACT_MULTIPLIER = 100


def get_fetcher():
    """Alpaca if keys present, else yfinance fallback (simulated option bars)."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher
    if ALPACA_AVAILABLE:
        f = AlpacaFetcher.from_env()
        if f is not None:
            return f, "Alpaca Markets API"
    return YFinanceFetcher(), "yfinance (set ALPACA_API_KEY for real option data)"


def contracts_for(entry_price: float, budget: float) -> int:
    """MAX(1, CEILING(budget / (entry_price * 100)))."""
    per_contract_cost = entry_price * CONTRACT_MULTIPLIER
    if per_contract_cost <= 0:
        return 1
    return max(1, math.ceil(budget / per_contract_cost))


def price_at(prices: dict, target_minute: int, tolerance: int) -> float | None:
    """Close at target_minute, else the nearest available minute within tolerance."""
    if target_minute in prices:
        return prices[target_minute]
    for delta in range(1, tolerance + 1):
        for m in (target_minute - delta, target_minute + delta):
            if m in prices:
                return prices[m]
    return None


def _representative(records: list) -> dict | None:
    """One usable ATM-call capture: prefer REAL bars, then strike closest to spot."""
    usable = [r for r in records if r["source"] != SOURCE_NO_STOCK and r["prices"]]
    if not usable:
        return None
    real = [r for r in usable if r["source"] == SOURCE_REAL]
    pool = real or usable
    return min(pool, key=lambda r: abs(r["strike"] - r["spot_open"]))


def build_trades(records_by_date: dict, cfg: Config) -> list:
    """One trade row per day for the fixed entry/exit clock."""
    entry_lbl = minute_to_str(cfg.entry_minute)
    exit_lbl = minute_to_str(cfg.exit_minute)
    tol = cfg.price_tolerance_minutes
    rows = []

    for d in sorted(records_by_date.keys()):
        rep = _representative(records_by_date[d])
        if rep is None:
            continue
        prices = rep["prices"]
        entry = price_at(prices, cfg.entry_minute, tol)
        exit_ = price_at(prices, cfg.exit_minute, tol)
        src = "REAL" if rep["source"] == SOURCE_REAL else "SIM"

        if entry is None or exit_ is None or entry <= 0:
            rows.append({
                "date": str(d), "contract_symbol": rep["contract"],
                "strike": rep["strike"], "source": src,
                "entry_time": entry_lbl, "entry_price": "",
                "exit_time": exit_lbl, "exit_price": "",
                "contracts": "", "cost_dollars": "", "pnl_dollars": "",
                "profitable": "", "note": "no usable price in entry/exit window",
            })
            continue

        qty = contracts_for(entry, cfg.per_trade_budget)
        payoff = exit_ - entry
        pnl = payoff * CONTRACT_MULTIPLIER * qty
        rows.append({
            "date": str(d), "contract_symbol": rep["contract"],
            "strike": rep["strike"], "source": src,
            "entry_time": entry_lbl, "entry_price": round(entry, 4),
            "exit_time": exit_lbl, "exit_price": round(exit_, 4),
            "contracts": qty,
            "cost_dollars": round(entry * CONTRACT_MULTIPLIER * qty, 2),
            "pnl_dollars": round(pnl, 2),
            "profitable": payoff > 0, "note": rep.get("note", ""),
        })
    return rows


def source_label(rows: list) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED real + Black-Scholes sim"
    if "REAL" in srcs:
        return "REAL Alpaca option bars"
    if "SIM" in srcs:
        return "SIMULATED (Black-Scholes)"
    return "NONE"


def _drawdown_and_sharpe(pnls: list) -> tuple[float, float]:
    """Pure-Python max drawdown and per-trade Sharpe (no numpy dependency)."""
    if not pnls:
        return 0.0, 0.0
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    n = len(pnls)
    mean = sum(pnls) / n
    if n > 1:
        var = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        std = var ** 0.5
        sharpe = (mean / std) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return round(max_dd, 2), round(sharpe, 3)


def compute_metrics(rows: list, cfg: Config) -> dict:
    """Aggregate the per-day rows into the P/L check metrics."""
    traded = [r for r in rows if r["pnl_dollars"] != ""]
    pnls = [r["pnl_dollars"] for r in traded]
    n = len(pnls)
    if n == 0:
        return {
            "n_trades": 0, "n_skipped": len(rows) - n, "wins": 0, "losses": 0,
            "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
            "biggest_win": 0.0, "biggest_loss": 0.0,
            "gross_profit": 0.0, "gross_loss": 0.0,
            "profit_concentration": 0.0, "loss_concentration": 0.0,
            "premium_spent": 0.0, "return_on_spend": 0.0,
            "max_drawdown": 0.0, "sharpe": 0.0,
            "total_contracts": 0, "data_source": source_label(rows),
        }

    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = sum(p for p in pnls if p < 0)
    biggest_win = max(pnls)
    biggest_loss = min(pnls)
    costs = [r["cost_dollars"] for r in traded
             if isinstance(r.get("cost_dollars"), (int, float))]
    premium = sum(costs) if costs else 0.0
    total_contracts = sum(r["contracts"] for r in traded
                          if isinstance(r.get("contracts"), int))
    max_dd, sharpe = _drawdown_and_sharpe(pnls)

    # Concentration: share of all winning $ that came from the single biggest win
    # (and the mirror for losses). ~1.0 => one trade drove the result.
    profit_conc = (biggest_win / gross_profit) if gross_profit > 0 else 0.0
    loss_conc = (biggest_loss / gross_loss) if gross_loss < 0 else 0.0

    return {
        "n_trades": n,
        "n_skipped": len(rows) - n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": round(wins / n, 4),
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / n, 2),
        "biggest_win": round(biggest_win, 2),
        "biggest_loss": round(biggest_loss, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_concentration": round(profit_conc, 4),
        "loss_concentration": round(loss_conc, 4),
        "premium_spent": round(premium, 2),
        "return_on_spend": round((total / premium) if premium else 0.0, 4),
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "total_contracts": total_contracts,
        "data_source": source_label(rows),
    }


def run(cfg: Config | None = None) -> tuple[list, dict, str]:
    """Capture data, build the per-day trades, and compute metrics.

    Returns (trade_rows, metrics, data_source_label).
    """
    cfg = cfg or Config()
    fetcher, source = get_fetcher()

    backtester = Backtester(fetcher, cfg)
    backtester.run(cfg.tickers)

    # TSLA calls only.
    records = backtester.daily_capture.get(("TSLA", "C"), [])
    by_date: dict = {}
    for r in records:
        by_date.setdefault(r["date"], []).append(r)

    rows = build_trades(by_date, cfg)
    metrics = compute_metrics(rows, cfg)
    return rows, metrics, source
