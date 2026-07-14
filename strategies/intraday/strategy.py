#!/usr/bin/env python
"""
PIPELINE ADAPTER for the ALL-DAYS INTRADAY optimal entry/exit time-frame study.

One run covers every weekday as its own same-session (buy & sell that day) intraday
study, each with its own expiry, lookback, and ticker set (see config.DAY_SPECS):

    Day        Entry      Expiry       DTE   Lookback  Tickers
    Monday     Monday     Monday       0DTE  150 d     Mag7 − META (6)
    Tuesday    Tuesday    Wednesday    1DTE  150 d     Mag7 − META (6)
    Wednesday  Wednesday  Wednesday    0DTE  150 d     Mag7 − META (6)
    Thursday   Thursday   Friday       1DTE  730 d     Mag7 − META + AMD + ORCL (8)
    Friday     Friday     Friday       0DTE  730 d     Mag7 − META + AMD + ORCL (8)

For each (day, ticker, call/put) it finds the best intraday entry window and exit
window over the full 9:30 AM–4:00 PM ET session (win_rate × avg_payoff), so the
whole week's suggested schedule is in one metrics.json → days map.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It writes to STRATEGY_RESULTS_DIR (falls back to ./output):
  - metrics.json      machine-readable metrics, keyed by day  (REQUIRED)
  - trades.csv        combined per-session ledger (a `day` column tags each row)
  - equity_curve.png  cumulative P&L, one line per weekday
  plus the rich per-day/per-ticker *.txt / *.csv the engine produces.
It prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block and exits 0 on
success; on error writes metrics.json {"status":"error"} and exits 1.

Data: real Alpaca option bars when the given expiry contract exists, otherwise a
Black-Scholes fallback (per-day/per-leg `data_source` reports which).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone as dt_timezone

DAYNAME = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


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


def _frame_summary(frame, summ, rows=None, ticker=None, opt_type=None):
    from timeframe_engine import frame_label
    data_source = _source_label(rows or [])
    label = {"ticker": ticker,
             "opt_type": ("CALL" if opt_type == "C" else "PUT") if opt_type else None}
    if frame is None:
        return {**label, "entry_frame": None, "exit_frame": None, "n_trades": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                "best_day": 0.0, "worst_day": 0.0,
                "return_on_spend": 0.0, "data_source": data_source}
    cost = summ.get("total_cost", 0.0)
    roi = (summ["total_pnl"] / cost) if cost else 0.0
    return {
        **label,
        "entry_frame": frame_label(frame["es"], frame["ee"]),
        "exit_frame": frame_label(frame["xs"], frame["xe"]),
        "entry_minutes": frame["ee"] - frame["es"],
        "exit_minutes": frame["xe"] - frame["xs"],
        "n_trades": summ["n"], "wins": summ["wins"],
        "win_rate": round(summ["win_rate"], 4),
        "total_pnl": round(summ["total_pnl"], 2),
        "avg_pnl": round(summ["avg_pnl"], 2),
        "best_day": round(summ["best"], 2), "worst_day": round(summ["worst"], 2),
        "premium_spent": round(cost, 2), "return_on_spend": round(roi, 4),
        "data_source": data_source,
    }


def _aggregate(all_rows):
    """Overall metrics over a flat list of per-session rows."""
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


def _day_block(all_results, spec):
    """Build one day's metrics block (aggregate + per-leg frames). Returns
    (block, all_rows) so the driver can pool rows for the portfolio total."""
    all_rows, legs = [], {}
    for (ticker, opt_type), res in sorted(all_results.items()):
        rows = res.get("rows", []) if res else []
        all_rows.extend(rows)
        key = f"{ticker}_{'CALL' if opt_type == 'C' else 'PUT'}"
        legs[key] = _frame_summary(res.get("frame") if res else None,
                                   res.get("summ", {}) if res else {}, rows,
                                   ticker=ticker, opt_type=opt_type)
    block = _aggregate(all_rows)
    entry_wd, exp_wd = spec["weekday"], spec["expiry_weekday"]
    dte = "0DTE" if exp_wd == entry_wd else "1DTE"
    block.update({
        "entry_day": spec["name"],
        "expiry": f"{DAYNAME[exp_wd]} ({dte})",
        "dte": dte,
        "lookback_days": spec["lookback"],
        "tickers": list(spec["tickers"]),
        "legs": legs,
    })
    return block, all_rows


def save_artifacts(out_dir, by_day):
    """Combined trades.csv (one `day` column) + equity_curve.png (a line per day)."""
    import csv

    path = os.path.join(out_dir, "trades.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["day", "date", "opt_type", "contract_symbol", "strike", "source",
                    "entry_frame", "entry_price", "exit_frame", "exit_price",
                    "payoff_per_share", "contracts", "cost_dollars", "pnl_dollars",
                    "profitable", "note"])
        for day, all_results in by_day.items():
            for (ticker, opt_type), res in sorted(all_results.items()):
                if not res:
                    continue
                for r in res.get("rows", []):
                    w.writerow([day, r["date"], r["opt_type"], r["contract_symbol"],
                                r["strike"], r["source"], r["entry_frame"],
                                r["entry_price"], r["exit_frame"], r["exit_price"],
                                r["payoff_per_share"], r["contracts"],
                                r["cost_dollars"], r["pnl_dollars"], r["profitable"],
                                r["note"]])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        plotted = False
        for day, all_results in by_day.items():
            pnls = []
            for (_, _), res in sorted(all_results.items()):
                if not res:
                    continue
                pnls.extend(r["pnl_dollars"] for r in res.get("rows", [])
                            if r["pnl_dollars"] != "")
            if not pnls:
                continue
            equity, cum = [], 0.0
            for p in pnls:
                cum += p
                equity.append(cum)
            ax.plot(range(1, len(equity) + 1), equity, lw=1.8, label=day)
            plotted = True
        if plotted:
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — intraday optimal entry/exit, per weekday")
            ax.set_xlabel("Trade # (within the day's book)")
            ax.set_ylabel("Cumulative P&L ($)")
            ax.legend()
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "equity_curve.png"), dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics):
    print("\n" + "=" * 78)
    print("  STRATEGY SUMMARY — ALL-DAYS INTRADAY optimal entry/exit")
    print("=" * 78)
    port = metrics.get("portfolio") or {}
    print(f"  Portfolio (all days): {port.get('n_trades', 0)} trades · "
          f"win {port.get('win_rate', 0) * 100:.1f}% · "
          f"total ${port.get('total_pnl', 0):,.0f} · "
          f"data {port.get('data_source')}")
    for name in metrics.get("days_order", []):
        b = metrics["days"][name]
        print("\n  " + "-" * 74)
        print(f"  {name.upper()}  (entry {name}, expiry {b['expiry']}, "
              f"lookback {b['lookback_days']}d, {len(b['tickers'])} tickers)")
        print(f"    {b.get('n_trades')} trades · win {b.get('win_rate', 0) * 100:.1f}% "
              f"· total ${b.get('total_pnl', 0):,.0f} · {b.get('data_source')}")
        for key, leg in (b.get("legs") or {}).items():
            print(f"      {key:<11}: {str(leg.get('entry_frame')):>15} → "
                  f"{str(leg.get('exit_frame')):>15}  "
                  f"(win {leg.get('win_rate', 0) * 100:.0f}%, "
                  f"${leg.get('total_pnl', 0):,.0f})")
    print("=" * 78 + "\n")
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
        import timeframe_engine as te
        from backtest_timeframe import TARGET_SPEND, size_fn, score_key, eligible
        from config import Config, DAY_SPECS, MAG6, MAG6_PLUS

        te.RESULTS_DIR = out_dir  # rich per-day TXT/CSV land in the results dir

        by_day, days, portfolio_rows = {}, {}, []
        for spec in DAY_SPECS:
            cfg = Config(
                tickers=list(spec["tickers"]),
                entry_weekday=spec["weekday"],
                expiry_weekday=spec["expiry_weekday"],
                backtest_days=spec["lookback"],
            )
            all_results = te.run_timeframe(
                lookback_days=spec["lookback"],
                method_label=(f"{spec['name']} intraday — MAX EXPECTED PROFIT, "
                              f"target-spend sized (win_rate × avg_payoff)"),
                score_key=score_key,
                eligible=eligible,
                size_fn=size_fn,
                file_tag=f"intraday_{spec['name'].lower()}",
                outlier_max=None,          # single pass per day; keep output simple
                header_extra=(
                    f"{spec['name']} entry → {DAYNAME[spec['expiry_weekday']]} expiry, "
                    f"lookback {spec['lookback']}d, tickers "
                    f"{', '.join(spec['tickers'])}."),
                config=cfg,
            )
            by_day[spec["name"]] = all_results
            block, rows = _day_block(all_results, spec)
            days[spec["name"]] = block
            portfolio_rows.extend(rows)

        metrics = {
            "status": "ok",
            "strategy": "intraday",
            "session": "9:30 AM-4:00 PM ET",
            "trade": "same-session intraday (buy & sell the entry day)",
            "universe": {"base_all_days": MAG6, "thursday_friday_add": ["AMD", "ORCL"]},
            "target_spend": TARGET_SPEND,
            "days_order": [s["name"] for s in DAY_SPECS],
            "days": days,
            "portfolio": _aggregate(portfolio_rows),
            "generated_at": datetime.now(dt_timezone.utc).isoformat(),
        }
        save_artifacts(out_dir, by_day)
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "intraday",
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
