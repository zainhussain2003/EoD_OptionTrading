#!/usr/bin/env python
"""
PIPELINE ADAPTER for the MWF concentration-capped time-schedule study.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone analysis in backtest_concentration.py /
concentration_engine.py and emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - trades.csv        per-day ledger (all ticker/day/option-type combos)
       - equity_curve.png  cumulative P&L chart
       - concentration_report.txt  the full plain-text terminal report
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The research logic lives in concentration_engine.py / backtest_concentration.py —
this file only adapts it to the pipeline. Run `python backtest_concentration.py`
for the terminal report, or `python strategy.py` to also produce the artifacts.
"""
from __future__ import annotations

import contextlib
import csv
import io
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


def _combo_summary(res):
    """Per (ticker, day, opt_type) block for metrics.json. Reports the chosen
    entry/exit, win rate, total P&L, and the winning single_trade_share of the
    chosen schedule (so it's visible the cap held)."""
    from concentration_engine import CONTRACT_MULTIPLIER
    from utils.date_utils import minute_to_str
    if res is None or res.get("best") is None:
        return {"chosen": False, "entry_time": None, "exit_time": None,
                "n_trades": 0, "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                "single_trade_share": None, "largest_win": 0.0,
                "return_on_spend": 0.0, "data_source": "NONE"}
    best = res["best"]
    summ = res["summ"]
    rows = res["rows"]
    cost = summ.get("total_cost", 0.0)
    roi = (summ["total_pnl"] / cost) if cost else 0.0
    share = best.get("single_trade_share")
    largest = (best.get("max_win") or 0.0) * CONTRACT_MULTIPLIER
    return {
        "chosen": True,
        "entry_time": minute_to_str(best["entry"]),
        "exit_time": minute_to_str(best["exit"]),
        "lookback_days": res.get("lookback_days"),
        "n_trades": summ["n"], "wins": summ["wins"],
        "win_rate": round(summ["win_rate"], 4),
        "total_pnl": round(summ["total_pnl"], 2),
        "avg_pnl": round(summ["avg_pnl"], 2),
        "best_day": round(summ["best"], 2), "worst_day": round(summ["worst"], 2),
        "largest_win": round(largest, 2),
        "single_trade_share": round(share, 4) if share is not None else None,
        "premium_spent": round(cost, 2), "return_on_spend": round(roi, 4),
        "n_skipped": summ["n_skipped"],
        "data_source": _source_label(rows),
    }


def _write_trades_csv(path, all_results):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "day_of_week", "opt_type", "date", "contract_symbol",
                    "strike", "source", "entry_time", "entry_price", "exit_time",
                    "exit_price", "payoff_per_share", "contracts", "cost_dollars",
                    "pnl_dollars", "profitable", "note"])
        for (ticker, day_name, opt_type), res in sorted(all_results.items()):
            if not res:
                continue
            for r in res["rows"]:
                w.writerow([ticker, day_name, opt_type, r["date"],
                            r["contract_symbol"], r["strike"], r["source"],
                            r["entry_time"], r["entry_price"], r["exit_time"],
                            r["exit_price"], r["payoff_per_share"], r["contracts"],
                            r["cost_dollars"], r["pnl_dollars"], r["profitable"],
                            r["note"]])


def save_artifacts(out_dir, all_results):
    """trades.csv (combined ledger) + equity_curve.png (one line per combo)."""
    _write_trades_csv(os.path.join(out_dir, "trades.csv"), all_results)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 6))
        plotted = False
        for (ticker, day_name, opt_type), res in sorted(all_results.items()):
            if not res:
                continue
            pnls = [r["pnl_dollars"] for r in res["rows"] if r["pnl_dollars"] != ""]
            if not pnls:
                continue
            equity, cum = [], 0.0
            for p in pnls:
                cum += p
                equity.append(cum)
            label = f"{ticker} {day_name[:3]} {'CALL' if opt_type == 'C' else 'PUT'}"
            ax.plot(range(1, len(equity) + 1), equity, lw=1.5, label=label)
            plotted = True
        if plotted:
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — MWF concentration-capped schedules")
            ax.set_xlabel("Trade # (chronological, per combo)")
            ax.set_ylabel("Cumulative P&L ($)")
            ax.legend(fontsize=8, ncol=2)
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "equity_curve.png"), dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


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


def build_metrics(all_results, max_single_trade_share, target_spend):
    """Aggregate the per-combo results into the contract metrics dict."""
    all_rows = []
    combos = {}
    for (ticker, day_name, opt_type), res in all_results.items():
        if res:
            all_rows.extend(res["rows"])
        key = f"{ticker}|{day_name}|{'calls' if opt_type == 'C' else 'puts'}"
        combos[key] = _combo_summary(res)

    metrics = {
        "status": "ok",
        "strategy": "mwf-concentration-capped",
        "tickers": ["TSLA", "AAPL"],
        "days": ["Monday", "Wednesday", "Friday"],
        "option_types": ["calls", "puts"],
        "ranking_metric": "win_rate x avg_payoff (max expected profit)",
        "max_single_trade_share": max_single_trade_share,
        "target_spend": target_spend,
        "eligibility": ("net_total_pnl > 0 AND "
                        "largest_single_win / net_total_pnl <= max_single_trade_share"),
        **_aggregate(all_rows),
        "combos": combos,
    }
    return metrics


def print_summary(metrics):
    print("\n" + "=" * 64)
    print("  STRATEGY SUMMARY — MWF concentration-capped schedules")
    print("=" * 64)
    print(f"  Concentration cap : single win ≤ "
          f"{metrics.get('max_single_trade_share', 0) * 100:.0f}% of net total P&L")
    print(f"  Data source       : {metrics.get('data_source')}")
    print(f"  Trades            : {metrics.get('n_trades')}")
    print(f"  Win rate          : {metrics.get('win_rate', 0) * 100:.1f}%")
    print(f"  Total P&L         : ${metrics.get('total_pnl', 0):,.2f}")
    print(f"  Avg / trade       : ${metrics.get('avg_pnl', 0):,.2f}")
    print(f"  Max drawdown      : ${metrics.get('max_drawdown', 0):,.2f}")
    for key, c in sorted(metrics.get("combos", {}).items()):
        if not c.get("chosen"):
            print(f"  {key:<22}: no eligible schedule")
            continue
        share = c.get("single_trade_share")
        share_s = f"{share * 100:.0f}%" if share is not None else "n/a"
        print(f"  {key:<22}: buy {c['entry_time']} sell {c['exit_time']}  "
              f"win {c['win_rate'] * 100:.0f}%  ${c['total_pnl']:,.0f}  "
              f"(top-win share {share_s})")
    print("=" * 64 + "\n")
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
        from backtest_concentration import (
            run_concentration, MAX_SINGLE_TRADE_SHARE, TARGET_SPEND,
        )

        # Capture the full terminal report into a plain-text artifact too.
        report_buf = io.StringIO()

        class _Tee(io.StringIO):
            def write(self, s):
                sys.__stdout__.write(s)
                return report_buf.write(s)

        with contextlib.redirect_stdout(_Tee()):
            all_results, _source = run_concentration(
                max_single_trade_share=MAX_SINGLE_TRADE_SHARE,
                target_spend=TARGET_SPEND)

        with open(os.path.join(out_dir, "concentration_report.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(report_buf.getvalue())

        metrics = build_metrics(all_results, MAX_SINGLE_TRADE_SHARE, TARGET_SPEND)
        save_artifacts(out_dir, all_results)
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "mwf-concentration-capped",
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
