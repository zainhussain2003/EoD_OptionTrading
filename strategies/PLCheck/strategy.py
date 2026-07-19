#!/usr/bin/env python
"""
PIPELINE ADAPTER for the TSLA CALLS end-of-day P/L check.

This is the entry point the EoD pipeline (Sentinel -> Forge -> Oracle -> Herald)
runs. It wraps eod_engine.py and emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - trades.csv        per-day ledger
       - equity_curve.png  cumulative P&L chart
  3. Prints the ===STRATEGY_SUMMARY_JSON=== ... ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The rule: buy the ATM TSLA call at 3:45 PM ET, sell at 3:55 PM ET, over the last
730 days (the Fridays TSLA trades 0DTE options). Contracts per trade =
MAX(1, CEILING($100 / (entry_price * 100))). Run by hand with
`python backtest_eod.py` for the terminal report, or `python strategy.py` to also
produce the contract artifacts.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from dataclasses import asdict
from datetime import datetime, timezone as dt_timezone


def results_dir() -> str:
    """Where artifacts go. Pipeline sets STRATEGY_RESULTS_DIR; CLI uses ./output."""
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


def write_trades_csv(path: str, rows: list) -> None:
    cols = ["date", "contract_symbol", "strike", "source", "entry_time",
            "entry_price", "exit_time", "exit_price", "contracts",
            "cost_dollars", "pnl_dollars", "profitable", "note"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])


def save_equity_curve(path: str, rows: list) -> None:
    pnls = [r["pnl_dollars"] for r in rows if r["pnl_dollars"] != ""]
    if not pnls:
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        equity, cum = [], 0.0
        for p in pnls:
            cum += p
            equity.append(cum)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(range(1, len(equity) + 1), equity, lw=1.8, color="#1f77b4")
        ax.axhline(0, color="grey", lw=0.8, ls="--")
        ax.set_title("Cumulative P&L — TSLA calls, buy 3:45 PM / sell 3:55 PM")
        ax.set_xlabel("Trade # (days)")
        ax.set_ylabel("Cumulative P&L ($)")
        fig.tight_layout()
        fig.savefig(path, dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics: dict) -> None:
    print("\n" + "=" * 60)
    print("  STRATEGY SUMMARY — TSLA calls, buy 3:45 PM / sell 3:55 PM ET")
    print("=" * 60)
    print(f"  Data source  : {metrics.get('data_source')}")
    print(f"  Trades       : {metrics.get('n_trades')}  "
          f"(skipped {metrics.get('n_skipped')})")
    print(f"  Win rate     : {metrics.get('win_rate', 0) * 100:.1f}%  "
          f"({metrics.get('wins')}W / {metrics.get('losses')}L)")
    print(f"  Total P&L    : ${metrics.get('total_pnl', 0):,.2f}")
    print(f"  Avg / trade  : ${metrics.get('avg_pnl', 0):,.2f}")
    print(f"  Biggest win  : ${metrics.get('biggest_win', 0):,.2f}")
    print(f"  Biggest loss : ${metrics.get('biggest_loss', 0):,.2f}")
    print(f"  Profit conc. : {metrics.get('profit_concentration', 0) * 100:.1f}% "
          f"of gross profit from the single biggest win")
    print(f"  Loss conc.   : {metrics.get('loss_concentration', 0) * 100:.1f}% "
          f"of gross loss from the single biggest loss")
    print(f"  Premium spent: ${metrics.get('premium_spent', 0):,.2f}   "
          f"return on spend: {metrics.get('return_on_spend', 0) * 100:+.1f}%")
    print(f"  Max drawdown : ${metrics.get('max_drawdown', 0):,.2f}   "
          f"Sharpe: {metrics.get('sharpe', 0)}")
    print("=" * 60 + "\n")
    print("===STRATEGY_SUMMARY_JSON===")
    print(json.dumps(metrics))
    print("===END_SUMMARY===")


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    out_dir = results_dir()

    if not os.environ.get("ALPACA_API_KEY") or not (
            os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")):
        print("  [data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — results will "
              "fall back to Black-Scholes simulation (yfinance has no option bars).")

    try:
        from config import Config
        import eod_engine as ee

        cfg = Config()
        rows, metrics, source = ee.run(cfg)

        metrics = {
            "status": "ok",
            "strategy": "PLCheck",
            "ticker": "TSLA",
            "option_type": "CALL",
            "entry_time": "3:45 PM ET",
            "exit_time": "3:55 PM ET",
            "lookback_days": cfg.backtest_days,
            "per_trade_budget": cfg.per_trade_budget,
            "sizing_rule": "contracts = MAX(1, CEILING(budget / (entry_price * 100)))",
            **metrics,
            "config": asdict(cfg),
            "generated_at": datetime.now(dt_timezone.utc).isoformat(),
        }

        write_trades_csv(os.path.join(out_dir, "trades.csv"), rows)
        save_equity_curve(os.path.join(out_dir, "equity_curve.png"), rows)
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "PLCheck",
                   "error": f"{type(e).__name__}: {e}", "traceback": tb}
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(tb, file=sys.stderr)
        print("===STRATEGY_SUMMARY_JSON===")
        print(json.dumps(metrics))
        print("===END_SUMMARY===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
