#!/usr/bin/env python
"""
PIPELINE ADAPTER for the MON/WED/FRI win-rate-capped 0DTE study.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone analysis in backtest_byday.py / byday_engine.py and
emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - trades.csv        per-day ledger (every ticker/day/type schedule)
       - equity_curve.png  cumulative P&L chart (one line per ticker+type)
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The research logic lives in backtest_byday.py / byday_engine.py — this file only
adapts it to the pipeline. Run `python backtest_byday.py` for the terminal report,
or `python strategy.py` to also produce the contract artifacts.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from datetime import datetime, timezone as dt_timezone


def results_dir() -> str:
    """Where artifacts go. Pipeline sets STRATEGY_RESULTS_DIR; CLI uses ./output."""
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


def _source_label(rows) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED real + Black-Scholes sim"
    if "REAL" in srcs:
        return "REAL Alpaca option bars"
    if "SIM" in srcs:
        return "SIMULATED (Black-Scholes)"
    return "NONE"


def _drawdown_and_sharpe(pnls):
    """Pure-Python max drawdown and a per-trade Sharpe (no numpy dependency)."""
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


def _aggregate(all_rows):
    """Overall metrics over a flat list of per-day rows."""
    pnls = [r["pnl_dollars"] for r in all_rows if r["pnl_dollars"] != ""]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls)
    max_dd, sharpe = _drawdown_and_sharpe(pnls)
    return {
        "n_trades": n,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / n, 2) if n else 0.0,
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "data_source": _source_label(all_rows),
    }


def _schedule_entry(ticker, day, opt_type, res):
    """One row of the by_schedule table for a (ticker, day, opt_type)."""
    from utils.date_utils import minute_to_str
    base = {"ticker": ticker, "day": day,
            "opt_type": "call" if opt_type == "C" else "put"}
    if not res:
        base.update({"entry_time": None, "exit_time": None, "n_trades": 0,
                     "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                     "best_day": 0.0, "worst_day": 0.0, "return_on_spend": 0.0,
                     "eligible": False})
        return base
    b, s = res["best"], res["summ"]
    ws, we = res["window"]
    cost = s.get("total_cost", 0.0)
    roi = (s["total_pnl"] / cost) if cost else 0.0
    base.update({
        "entry_time": minute_to_str(b["entry"]),
        "exit_time": minute_to_str(b["exit"]),
        "window": f"{ws}:00-{we}:00 ET",
        "lookback_days": res["lookback"],
        "n_trades": s["n"], "wins": s["wins"],
        "win_rate": round(s["win_rate"], 4),
        "total_pnl": round(s["total_pnl"], 2),
        "avg_pnl": round(s["avg_pnl"], 2),
        "best_day": round(s["best"], 2), "worst_day": round(s["worst"], 2),
        "premium_spent": round(cost, 2), "return_on_spend": round(roi, 4),
        "eligible": True,
    })
    return base


def _rows_for(all_results, predicate):
    out = []
    for (ticker, day, opt_type), res in all_results.items():
        if res and predicate(ticker, day, opt_type):
            out.extend(res["rows"])
    return out


def build_metrics(all_results, run_meta):
    """Aggregate per (ticker, day, opt_type) results into the contract metrics."""
    all_rows = _rows_for(all_results, lambda t, d, o: True)
    metrics = {
        "status": "ok",
        "strategy": "mwf-winrate-capped",
        "tickers": run_meta["tickers"],
        "days": ["Monday", "Wednesday", "Friday"],
        "option_types": ["call", "put"],
        "target_spend": run_meta["target_spend"],
        "win_rate_target": run_meta["win_rate_target"],
        "win_rate_band": run_meta["win_rate_band"],
        "schedule": [
            {"day": d, "lookback_days": lb, "window": f"{ws}:00-{we}:00 ET"}
            for (d, _wd, lb, ws, we) in run_meta["schedule"]
        ],
        **_aggregate(all_rows),
    }
    # Per option type
    metrics["calls"] = _aggregate(_rows_for(all_results, lambda t, d, o: o == "C"))
    metrics["puts"] = _aggregate(_rows_for(all_results, lambda t, d, o: o == "P"))
    # Per weekday
    metrics["by_day"] = {
        day: _aggregate(_rows_for(all_results, lambda t, d, o, _dn=day: d == _dn))
        for day in ["Monday", "Wednesday", "Friday"]
    }
    # Every chosen schedule (the "best day" per ticker/day/type)
    metrics["by_schedule"] = [
        _schedule_entry(t, d, o, all_results.get((t, d, o)))
        for t in run_meta["tickers"]
        for d in ["Monday", "Wednesday", "Friday"]
        for o in run_meta["option_types"]
    ]
    return metrics


def write_trades_csv(path, all_results):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "day_of_week", "opt_type", "date", "contract_symbol",
                    "strike", "source", "entry_time", "entry_price", "exit_time",
                    "exit_price", "payoff_per_share", "contracts", "cost_dollars",
                    "pnl_dollars", "profitable", "note"])
        for (ticker, day, opt_type), res in sorted(all_results.items()):
            if not res:
                continue
            for r in res["rows"]:
                w.writerow([ticker, day, r["opt_type"], r["date"],
                            r["contract_symbol"], r["strike"], r["source"],
                            r["entry_time"], r["entry_price"], r["exit_time"],
                            r["exit_price"], r["payoff_per_share"], r["contracts"],
                            r["cost_dollars"], r["pnl_dollars"], r["profitable"],
                            r["note"]])


def save_equity_curve(path, all_results, tickers, option_types):
    """One cumulative-P&L line per (ticker, opt_type), Mon→Wed→Fri by date."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        plotted = False
        for ticker in tickers:
            for opt_type in option_types:
                rows = []
                for day in ["Monday", "Wednesday", "Friday"]:
                    res = all_results.get((ticker, day, opt_type))
                    if res:
                        rows.extend(res["rows"])
                pnls = [(r["date"], r["pnl_dollars"]) for r in rows
                        if r["pnl_dollars"] != ""]
                pnls.sort(key=lambda x: x[0])
                if not pnls:
                    continue
                equity, cum = [], 0.0
                for _d, p in pnls:
                    cum += p
                    equity.append(cum)
                label = f"{ticker} {'CALL' if opt_type == 'C' else 'PUT'}s"
                ax.plot(range(1, len(equity) + 1), equity, lw=1.8, label=label)
                plotted = True
        if plotted:
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — Mon/Wed/Fri win-rate-capped 0DTE")
            ax.set_xlabel("Trade # (chronological)")
            ax.set_ylabel("Cumulative P&L ($)")
            ax.legend()
            fig.tight_layout()
            fig.savefig(path, dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics):
    c, p = metrics.get("calls") or {}, metrics.get("puts") or {}
    print("\n" + "=" * 62)
    print("  STRATEGY SUMMARY — Mon/Wed/Fri win-rate-capped 0DTE")
    print("=" * 62)
    band = metrics.get("win_rate_band", [0, 0])
    print(f"  Tickers     : {', '.join(metrics.get('tickers', []))}")
    print(f"  Win-rate cap: best day in [{band[0]:.0%}, {band[1]:.0%}]")
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Trades      : {metrics.get('n_trades')}")
    print(f"  Win rate    : {metrics.get('win_rate', 0) * 100:.1f}%")
    print(f"  Total P&L   : ${metrics.get('total_pnl', 0):,.2f}")
    print(f"  Avg / trade : ${metrics.get('avg_pnl', 0):,.2f}")
    print(f"  Max drawdown: ${metrics.get('max_drawdown', 0):,.2f}")
    print(f"  CALLS       : win {c.get('win_rate', 0) * 100:.0f}%  "
          f"${c.get('total_pnl', 0):,.0f}  ({c.get('n_trades', 0)} trades)")
    print(f"  PUTS        : win {p.get('win_rate', 0) * 100:.0f}%  "
          f"${p.get('total_pnl', 0):,.0f}  ({p.get('n_trades', 0)} trades)")
    print("=" * 62 + "\n")
    # Machine-readable block — Oracle / log scrapers key off these markers.
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
        from backtest_byday import run_all

        all_results, run_meta = run_all()
        metrics = build_metrics(all_results, run_meta)
        metrics["data_source"] = run_meta["data_source"] if metrics["n_trades"] == 0 \
            else metrics["data_source"]

        write_trades_csv(os.path.join(out_dir, "trades.csv"), all_results)
        save_equity_curve(os.path.join(out_dir, "equity_curve.png"), all_results,
                          run_meta["tickers"], run_meta["option_types"])
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "mwf-winrate-capped",
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
