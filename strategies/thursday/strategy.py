#!/usr/bin/env python
"""
PIPELINE ADAPTER — THURSDAY entry → FRIDAY expiry, AAPL & TSLA, CALLS & PUTS.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone Thu→Fri study in thu_fri_engine.py and emits the
pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - trades.csv        per-weekly-pair ledger (each ticker × call/put)
       - equity_curve.png  cumulative P&L per leg
     plus the rich per-run *.txt / *.csv the standalone engine produces.
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The research question — "what is the best time to buy on Thursday and sell for a
Friday expiry, for AAPL and TSLA?" — is answered per leg (ticker × call/put):
for every entry minute (3:55–3:59 PM ET) and every return target we measure the
limit-at-target-else-sell-at-3:55 strategy, then report the single best-netting
(entry minute, target) combo as that leg's recommendation.

Run by hand with `python strategy.py`.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone as dt_timezone

# ── knobs ─────────────────────────────────────────────────────────────────
LOOKBACK_DAYS = 365                       # calendar days of history to test
RETURN_MULTIPLES = [1.0, 1.5, 2.0, 2.5]   # profit targets (× premium paid)
CONTRACT_MULTIPLIER = 100                 # 1 option = 100 shares


def results_dir() -> str:
    """Where artifacts go. Pipeline sets STRATEGY_RESULTS_DIR; CLI uses ./output."""
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


def _bridge_alpaca_secret() -> None:
    """The pipeline contract names the secret ALPACA_SECRET_KEY, but the fetcher
    reads ALPACA_API_SECRET. Mirror one onto the other so either works."""
    if not os.environ.get("ALPACA_API_SECRET") and os.environ.get("ALPACA_SECRET_KEY"):
        os.environ["ALPACA_API_SECRET"] = os.environ["ALPACA_SECRET_KEY"]


def _source_label(samples) -> str:
    from models import SOURCE_REAL, SOURCE_SIM
    srcs = {s["source"] for s in samples}
    if SOURCE_REAL in srcs and SOURCE_SIM in srcs:
        return "MIXED real + Black-Scholes sim"
    if SOURCE_REAL in srcs:
        return "REAL Alpaca option bars"
    if SOURCE_SIM in srcs:
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


def _best_config(engine, samples):
    """Pick the (entry minute, target) with the best net $ per $100 staked.

    Returns (minute, multiple, strategy_stats_dict) or (None, None, None) if no
    combo has enough samples.
    """
    best = None
    for minute in engine.ENTRY_MINUTES:
        for m in RETURN_MULTIPLES:
            ss = engine.strategy_stats(samples, minute, m)
            if ss is None:
                continue
            if best is None or ss["net_per_100"] > best[2]["net_per_100"]:
                best = (minute, m, ss)
    return best if best is not None else (None, None, None)


def _replay_leg(engine, samples, minute, m):
    """Replay every weekly pair at (minute, target m). Returns list of trade dicts
    (one per pair) with real dollar P&L on 1 contract."""
    trades = []
    for s in samples:
        ep = s["entries"].get(minute)
        xp = s.get("exp_exit_price")
        if ep is None or ep <= 0 or xp is None:
            continue
        target = ep * (1.0 + m)
        hit = s.get("exp_high_to_exit")
        if hit is not None and hit >= target:
            sell, filled = target, True
        else:
            sell, filled = xp, False
        cost = ep * CONTRACT_MULTIPLIER
        pnl = (sell - ep) * CONTRACT_MULTIPLIER
        trades.append({
            "ticker": s["ticker"], "opt_type": s["opt_type"],
            "entry_date": str(s["entry_date"]), "expiry_date": str(s["expiry_date"]),
            "strike": s["strike"], "contract": s["contract"],
            "source": "REAL" if s["source"] == engine.SOURCE_REAL else "SIM",
            "entry_time": engine.minute_to_str(minute),
            "entry_price": round(ep, 4), "target_price": round(target, 4),
            "exit_price": round(sell, 4), "filled": filled,
            "cost_dollars": round(cost, 2), "pnl_dollars": round(pnl, 2),
            "profitable": pnl > 0,
        })
    return trades


def _leg_metrics(engine, ticker, opt_type, samples, minute, m, ss, trades):
    """Metrics block for one leg (ticker × call/put) at its best config."""
    touch = engine.minute_stats(samples, minute, RETURN_MULTIPLES) if minute else None
    pnls = [t["pnl_dollars"] for t in trades]
    total = sum(pnls)
    wins = sum(1 for p in pnls if p > 0)
    n = len(pnls)
    return {
        "ticker": ticker,
        "opt_type": "CALL" if opt_type == "C" else "PUT",
        "direction": "bet up" if opt_type == "C" else "bet down",
        "n_weekly_pairs": len(samples),
        "data_source": _source_label(samples),
        "best_entry_time": engine.minute_to_str(minute) if minute else None,
        "best_target_multiple": m,
        "best_net_per_100": round(ss["net_per_100"], 2) if ss else 0.0,
        "fill_rate": round(ss["fill_rate"], 4) if ss else 0.0,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "avg_entry_price": round(touch["avg_entry"], 4) if touch else 0.0,
        "touch_prob_at_best_target": (round(touch["probs"][m], 4)
                                      if touch and m in touch["probs"] else 0.0),
        "n_trades": n,
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / n, 2) if n else 0.0,
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
    }


def build_metrics(engine, by_key, config, all_trades, legs):
    pnls = [t["pnl_dollars"] for t in all_trades]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls)
    max_dd, sharpe = _drawdown_and_sharpe(pnls)
    all_samples = [s for samples in by_key.values() for s in samples]
    return {
        "status": "ok",
        "strategy": "thursday",
        "tickers": list(config.tickers),
        "option_types": ["CALL", "PUT"],
        "entry_day": "Thursday (rolls to Wednesday when Friday is a market holiday)",
        "expiry_day": "Friday (weekly)",
        "entry_window": "3:55-3:59 PM ET",
        "exit_rule": "rest a limit at the return target; if unfilled by 3:55 PM ET "
                     "on the expiry day, sell at 3:55 PM ET",
        "lookback_days": LOOKBACK_DAYS,
        "return_multiples": RETURN_MULTIPLES,
        "data_source": _source_label(all_samples),
        "n_trades": n,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / n, 2) if n else 0.0,
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "legs": legs,
    }


def save_artifacts(out_dir, all_trades, legs):
    """trades.csv (per-pair ledger) + equity_curve.png (cumulative P&L per leg)."""
    import csv

    csv_path = os.path.join(out_dir, "trades.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "opt_type", "entry_date", "expiry_date", "strike",
                    "contract", "source", "entry_time", "entry_price",
                    "target_price", "exit_price", "filled", "cost_dollars",
                    "pnl_dollars", "profitable"])
        for t in all_trades:
            w.writerow([t["ticker"], t["opt_type"], t["entry_date"], t["expiry_date"],
                        t["strike"], t["contract"], t["source"], t["entry_time"],
                        t["entry_price"], t["target_price"], t["exit_price"],
                        t["filled"], t["cost_dollars"], t["pnl_dollars"],
                        t["profitable"]])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        plotted = False
        # Group trades by leg, in chronological order, cumulative P&L.
        by_leg = {}
        for t in all_trades:
            by_leg.setdefault((t["ticker"], t["opt_type"]), []).append(t)
        for (ticker, opt_type), trades in sorted(by_leg.items()):
            trades = sorted(trades, key=lambda x: x["expiry_date"])
            equity, cum = [], 0.0
            for t in trades:
                cum += t["pnl_dollars"]
                equity.append(cum)
            if not equity:
                continue
            label = f"{ticker} {'CALL' if opt_type == 'C' else 'PUT'}s"
            ax.plot(range(1, len(equity) + 1), equity, lw=1.8, label=label)
            plotted = True
        if plotted:
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — Thursday→Friday AAPL/TSLA calls & puts "
                         "(1 contract, best entry/target per leg)")
            ax.set_xlabel("Trade # (weekly pairs)")
            ax.set_ylabel("Cumulative P&L ($)")
            ax.legend()
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "equity_curve.png"), dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def print_summary(metrics):
    print("\n" + "=" * 66)
    print("  STRATEGY SUMMARY — Thursday→Friday AAPL/TSLA calls & puts")
    print("=" * 66)
    print(f"  Data source : {metrics.get('data_source')}")
    print(f"  Trades      : {metrics.get('n_trades')}")
    print(f"  Win rate    : {metrics.get('win_rate', 0) * 100:.1f}%")
    print(f"  Total P&L   : ${metrics.get('total_pnl', 0):,.2f}")
    print(f"  Avg / trade : ${metrics.get('avg_pnl', 0):,.2f}")
    print(f"  Max drawdown: ${metrics.get('max_drawdown', 0):,.2f}")
    print("  Best entry/exit per leg (buy 3:55-3:59 Thu, sell limit-or-3:55 Fri):")
    for key, leg in (metrics.get("legs") or {}).items():
        print(f"    {key:<12}: buy {leg.get('best_entry_time')}  "
              f"target {leg.get('best_target_multiple')}x  "
              f"(win {leg.get('win_rate', 0) * 100:.0f}%, "
              f"fill {leg.get('fill_rate', 0) * 100:.0f}%, "
              f"${leg.get('total_pnl', 0):,.0f})")
    print("=" * 66 + "\n")
    print("===STRATEGY_SUMMARY_JSON===")
    print(json.dumps(metrics))
    print("===END_SUMMARY===")


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    _bridge_alpaca_secret()
    out_dir = results_dir()

    if not os.environ.get("ALPACA_API_KEY") or not (
            os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")):
        print("  [data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — results will "
              "fall back to Black-Scholes simulation (yfinance has no option bars).")

    try:
        import thu_fri_engine as engine
        from config import Config

        engine.RESULTS_DIR = out_dir       # deliver the rich TXT/CSV here too
        config = Config()

        by_key = engine.run(
            lookback_days=LOOKBACK_DAYS,
            multiples=RETURN_MULTIPLES,
            method_label="THURSDAY → FRIDAY AAPL/TSLA call & put probability",
        )

        # Per-leg best config → ledger → metrics.
        legs, all_trades = {}, []
        for ticker in config.tickers:
            for opt_type in config.option_types:
                samples = by_key.get((ticker, opt_type), [])
                minute, m, ss = _best_config(engine, samples)
                trades = _replay_leg(engine, samples, minute, m) if minute else []
                all_trades.extend(trades)
                key = f"{ticker}_{'CALL' if opt_type == 'C' else 'PUT'}"
                legs[key] = _leg_metrics(engine, ticker, opt_type, samples,
                                         minute, m, ss, trades)

        metrics = build_metrics(engine, by_key, config, all_trades, legs)
        save_artifacts(out_dir, all_trades, legs)
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "thursday",
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
