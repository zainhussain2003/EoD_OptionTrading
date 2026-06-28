#!/usr/bin/env python
"""
EoD OPTION-TRADING STRATEGY TEMPLATE
====================================

Reference implementation: a weekly out-of-the-money CASH-SECURED PUT-SELLING
strategy on SPY, backtested at end-of-day (3:55pm ET) entries.

This file is the standard structure every strategy in this repo follows. The
Architect agent COPIES this file into a new `strategies/<name>/` directory and
modifies the clearly-marked sections to implement a new idea. Sentinel validates
it, Forge runs it, Oracle reads its output, Herald reports it.

THE CONTRACT (do not break these — the rest of the pipeline depends on them):
  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into the directory given by env STRATEGY_RESULTS_DIR
     (falls back to ./output when run by hand). Produces:
        - metrics.json     machine-readable metrics  (REQUIRED)
        - trades.csv       per-trade ledger
        - equity_curve.png cumulative P&L chart
  3. Prints a fenced JSON summary block to stdout so it is greppable in logs:
        ===STRATEGY_SUMMARY_JSON===
        { ...metrics... }
        ===END_SUMMARY===
  4. Exits 0 on success. On an unrecoverable error, let the exception propagate
     (Forge captures the full traceback) OR write metrics.json with
     {"status":"error", ...} and exit non-zero.

Run by hand:   python strategy.py
Use `python`, not `python3` (this repo targets Windows).
"""
from __future__ import annotations

import json
import math
import os
import sys
import traceback
from dataclasses import asdict
from datetime import datetime, timedelta, timezone as dt_timezone

# Third-party (see requirements.txt). Imported lazily-ish so Sentinel can flag
# missing deps with a clean message rather than a raw ImportError mid-run.
import numpy as np
import pandas as pd

from config import Config


# ───────────────────────────────────────────────────────────────────────────
# SECTION 0 — OUTPUT LOCATION
# ───────────────────────────────────────────────────────────────────────────
def results_dir() -> str:
    """Where artifacts go. Pipeline sets STRATEGY_RESULTS_DIR; CLI uses ./output."""
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


# ───────────────────────────────────────────────────────────────────────────
# SECTION 1 — PRICING HELPERS
# Black–Scholes put price, used both for the delta solve and as the fallback
# when real Alpaca option bars are unavailable (mirrors the repo's existing
# REAL-vs-SIMULATED provenance approach).
# ───────────────────────────────────────────────────────────────────────────
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_put_price(spot, strike, t_years, sigma, r) -> float:
    if t_years <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))
    d2 = d1 - sigma * math.sqrt(t_years)
    return strike * math.exp(-r * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def bs_put_delta(spot, strike, t_years, sigma, r) -> float:
    if t_years <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))
    return _norm_cdf(d1) - 1.0  # put delta in [-1, 0]


def strike_for_target_delta(spot, t_years, sigma, r, target_delta, otm_pct_fallback):
    """Find the OTM strike whose put delta ≈ -target_delta. Falls back to a
    fixed %-OTM strike if the search degenerates."""
    target = -abs(target_delta)
    lo, hi = spot * 0.50, spot * 0.999
    if sigma <= 0:
        return round(spot * (1 - otm_pct_fallback))
    for _ in range(60):
        mid = (lo + hi) / 2
        d = bs_put_delta(spot, mid, t_years, sigma, r)
        if d < target:   # too far OTM (delta closer to 0 is higher strike); adjust
            lo = mid
        else:
            hi = mid
    strike = round((lo + hi) / 2)
    if not (spot * 0.5 < strike < spot):
        strike = round(spot * (1 - otm_pct_fallback))
    return float(strike)


# ───────────────────────────────────────────────────────────────────────────
# SECTION 2 — DATA LOADING
# Pull underlying daily bars from Alpaca. If keys are missing or the request
# fails, fall back to a reproducible simulated price path so the pipeline always
# produces output (data_source is recorded in metrics.json either way).
# ───────────────────────────────────────────────────────────────────────────
def load_underlying(cfg: Config, ticker: str):
    """Return (DataFrame[date, close], data_source_str)."""
    end = datetime.now(dt_timezone.utc)
    start = end - timedelta(days=cfg.lookback_days)

    api_key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")

    if api_key and secret:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            client = StockHistoricalDataClient(api_key, secret)
            req = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars = client.get_stock_bars(req).df
            if bars is not None and len(bars) > 0:
                df = bars.reset_index()
                # MultiIndex (symbol, timestamp) -> columns
                df = df[df["symbol"] == ticker] if "symbol" in df.columns else df
                out = pd.DataFrame({
                    "date": pd.to_datetime(df["timestamp"]).dt.tz_convert(cfg.timezone).dt.date,
                    "close": df["close"].astype(float).values,
                })
                return out.reset_index(drop=True), "REAL Alpaca stock bars"
        except Exception as e:  # noqa: BLE001 - degrade gracefully, record reason
            print(f"  [data] Alpaca fetch failed ({type(e).__name__}: {e}); using simulation.")

    # --- Simulated fallback (reproducible GBM) ---
    # Stable per-ticker seed (builtin hash() is salted per-process, so use hashlib).
    import hashlib
    n = cfg.lookback_days
    seed = int(hashlib.sha256(ticker.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    mu, sigma_daily = 0.08 / 252, 0.012
    rets = rng.normal(mu, sigma_daily, n)
    price = 500.0 * np.exp(np.cumsum(rets))
    dates = [(start + timedelta(days=i)).date() for i in range(n)]
    out = pd.DataFrame({"date": dates, "close": price})
    return out, "SIMULATED (no Alpaca keys / fetch failed)"


# ───────────────────────────────────────────────────────────────────────────
# SECTION 3 — STRATEGY LOGIC + BACKTEST
# EDIT THIS to implement a new idea. Here: each week, sell an OTM put at EoD,
# collect premium, settle at expiry intrinsic value.
# ───────────────────────────────────────────────────────────────────────────
def backtest(cfg: Config, prices: pd.DataFrame, ticker: str):
    prices = prices.sort_values("date").reset_index(drop=True)
    closes = prices["close"].values
    # realized vol estimate for pricing/sim
    rets = np.diff(np.log(closes))
    sigma_ann = float(np.std(rets) * math.sqrt(252)) if len(rets) > 1 else 0.20
    sigma_ann = max(sigma_ann, 0.05)

    r = cfg.risk_free_rate
    t_years = cfg.dte / 365.0
    step = max(cfg.dte, 1)

    trades = []
    for i in range(0, len(prices) - step, step):
        spot = float(closes[i])
        expiry_spot = float(closes[i + step])
        strike = strike_for_target_delta(
            spot, t_years, sigma_ann, r, cfg.target_delta, cfg.otm_pct_fallback
        )
        premium = bs_put_price(spot, strike, t_years, sigma_ann, r)  # credit received
        intrinsic = max(strike - expiry_spot, 0.0)                   # paid at expiry
        pnl = (premium - intrinsic) * cfg.contract_multiplier * cfg.contracts
        trades.append({
            "entry_date": str(prices["date"].iloc[i]),
            "expiry_date": str(prices["date"].iloc[i + step]),
            "ticker": ticker,
            "spot": round(spot, 2),
            "strike": strike,
            "premium": round(premium, 2),
            "expiry_spot": round(expiry_spot, 2),
            "pnl": round(pnl, 2),
            "win": pnl > 0,
        })
    return trades, sigma_ann


# ───────────────────────────────────────────────────────────────────────────
# SECTION 4 — METRICS
# These keys are the contract Oracle reads. Keep them present even on no-trade.
# ───────────────────────────────────────────────────────────────────────────
def compute_metrics(trades, data_source, sigma_ann) -> dict:
    if not trades:
        return {
            "status": "ok", "n_trades": 0, "win_rate": 0.0, "total_pnl": 0.0,
            "avg_pnl": 0.0, "max_drawdown": 0.0, "sharpe": 0.0,
            "data_source": data_source, "sigma_annualized": round(sigma_ann, 4),
        }
    pnls = np.array([t["pnl"] for t in trades], dtype=float)
    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    drawdown = equity - peak
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    sharpe = float(np.mean(pnls) / np.std(pnls) * math.sqrt(252 / max(1, _avg_step(trades)))) \
        if np.std(pnls) > 0 else 0.0
    return {
        "status": "ok",
        "n_trades": int(len(trades)),
        "win_rate": round(float(np.mean(pnls > 0)), 4),
        "total_pnl": round(float(pnls.sum()), 2),
        "avg_pnl": round(float(pnls.mean()), 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 3),
        "best_trade": round(float(pnls.max()), 2),
        "worst_trade": round(float(pnls.min()), 2),
        "data_source": data_source,
        "sigma_annualized": round(sigma_ann, 4),
    }


def _avg_step(trades):
    try:
        d0 = datetime.fromisoformat(trades[0]["entry_date"])
        d1 = datetime.fromisoformat(trades[0]["expiry_date"])
        return max((d1 - d0).days, 1)
    except Exception:
        return 7


# ───────────────────────────────────────────────────────────────────────────
# SECTION 5 — OUTPUT (artifacts + summary block)
# ───────────────────────────────────────────────────────────────────────────
def remove_outliers(trades, outlier_max):
    """Drop winning trades whose dollar P&L exceeds outlier_max (mirrors the
    repo's outliers-removed pass; the threshold is positive, so only fat-tail
    wins are removed)."""
    return [t for t in trades if t["pnl"] <= outlier_max]


def save_artifacts(out_dir, trades, metrics, cfg: Config, trades_no_outliers=None):
    # trades.csv
    cols = list(trades[0].keys()) if trades else None
    pd.DataFrame(trades, columns=cols).to_csv(
        os.path.join(out_dir, "trades.csv"), index=False)

    # trades_outliers_removed.csv — same structure, winning outliers (> outlier_max) dropped
    if trades_no_outliers is not None:
        pd.DataFrame(trades_no_outliers, columns=cols).to_csv(
            os.path.join(out_dir, "trades_outliers_removed.csv"), index=False)

    # equity_curve.png
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if trades:
            equity = np.cumsum([t["pnl"] for t in trades])
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(range(len(equity)), equity, lw=1.8)
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — EoD Put-Selling Template")
            ax.set_xlabel("Trade #")
            ax.set_ylabel("Cumulative P&L ($)")
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "equity_curve.png"), dpi=110)
            plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")

    # metrics.json (include the config used, for provenance)
    payload = dict(metrics)
    payload["config"] = asdict(cfg)
    payload["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def print_summary(metrics):
    print("\n" + "=" * 60)
    print("  STRATEGY SUMMARY")
    print("=" * 60)
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Trades      : {metrics.get('n_trades')}")
    print(f"  Win rate    : {metrics.get('win_rate', 0) * 100:.1f}%")
    print(f"  Total P&L   : ${metrics.get('total_pnl', 0):,.2f}")
    print(f"  Avg / trade : ${metrics.get('avg_pnl', 0):,.2f}")
    print(f"  Max drawdown: ${metrics.get('max_drawdown', 0):,.2f}")
    print(f"  Sharpe      : {metrics.get('sharpe', 0)}")
    print("=" * 60 + "\n")
    # Machine-readable block — Oracle / log scrapers key off these markers.
    print("===STRATEGY_SUMMARY_JSON===")
    print(json.dumps(metrics))
    print("===END_SUMMARY===")


# ───────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────
def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    cfg = Config()
    out_dir = results_dir()

    all_trades = []
    data_source = "UNKNOWN"
    sigma_ann = 0.0
    for ticker in cfg.tickers:
        prices, data_source = load_underlying(cfg, ticker)
        print(f"  Loaded {len(prices)} bars for {ticker} — {data_source}")
        trades, sigma_ann = backtest(cfg, prices, ticker)
        all_trades.extend(trades)

    metrics = compute_metrics(all_trades, data_source, sigma_ann)
    metrics["outlier_max"] = cfg.outlier_max

    # Outliers-removed view: drop winning trades over the threshold, recompute.
    trades_no_outliers = remove_outliers(all_trades, cfg.outlier_max)
    excl = compute_metrics(trades_no_outliers, data_source, sigma_ann)
    excl["outlier_max"] = cfg.outlier_max
    excl["n_removed"] = len(all_trades) - len(trades_no_outliers)
    metrics["outliers_removed"] = excl

    save_artifacts(out_dir, all_trades, metrics, cfg, trades_no_outliers)
    print_summary(metrics)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Record a structured error so Oracle/Herald can report it even on crash.
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        try:
            out_dir = results_dir()
            with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
                json.dump({"status": "error", "error": tb.splitlines()[-1], "traceback": tb}, f, indent=2)
        except Exception:
            pass
        sys.exit(1)
