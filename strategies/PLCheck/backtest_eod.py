#!/usr/bin/env python
"""
Standalone terminal report for the TSLA calls end-of-day P/L check.

Run by hand:  python backtest_eod.py
(Use `python`, not `python3` — this repo targets Windows.)

This prints a per-day ledger and the summary. The pipeline entry point is
strategy.py, which reuses the same engine and also writes metrics.json /
trades.csv / equity_curve.png.
"""
from __future__ import annotations

import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import Config
import eod_engine as ee


def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def green(t):  return _c(t, "32")
def red(t):    return _c(t, "31")
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "36")


def main() -> int:
    cfg = Config()

    print(bold("\n" + "=" * 92))
    print(bold("  TSLA CALLS — END-OF-DAY P/L CHECK"))
    print(bold(f"  Buy at {cfg.entry_minute // 60 % 12 or 12}:{cfg.entry_minute % 60:02d} PM"
               f"  ->  Sell at {cfg.exit_minute // 60 % 12 or 12}:{cfg.exit_minute % 60:02d} PM ET"))
    print(bold(f"  Lookback: {cfg.backtest_days} calendar days   "
               f"Sizing: contracts = MAX(1, CEILING(${cfg.per_trade_budget:.0f} / "
               f"(entry x 100)))"))
    print(bold("=" * 92))

    rows, metrics, source = ee.run(cfg)
    print(f"  Data source: {source}\n")

    # Per-day ledger
    print(f"  {'Date':<12} {'Strike':>8} {'Src':>4} {'Qty':>4} "
          f"{'Buy$':>8} {'Sell$':>8} {'Cost$':>9} {'P&L $':>11}  Result")
    print(f"  {'-'*12} {'-'*8} {'-'*4} {'-'*4} {'-'*8} {'-'*8} {'-'*9} {'-'*11}  {'-'*6}")
    for r in rows:
        if r["pnl_dollars"] == "":
            print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
                  f"{'-':>4} {'-':>8} {'-':>8} {'-':>9} {'-':>11}  "
                  + cyan("skip"))
            continue
        pnl = r["pnl_dollars"]
        pnl_s = green(f"${pnl:+,.2f}") if pnl > 0 else red(f"${pnl:+,.2f}")
        res = green("WIN ") if r["profitable"] else red("LOSS")
        print(f"  {r['date']:<12} {r['strike']:>8.1f} {r['source']:>4} "
              f"{r['contracts']:>4} {r['entry_price']:>8.2f} {r['exit_price']:>8.2f} "
              f"{r['cost_dollars']:>9,.2f} {pnl_s:>11}  {res}")

    m = metrics
    tot = m["total_pnl"]
    tot_s = green(f"${tot:+,.2f}") if tot >= 0 else red(f"${tot:+,.2f}")
    print()
    print(bold("  SUMMARY"))
    print(f"    Trades        : {m['n_trades']}  (skipped {m['n_skipped']})")
    print(f"    Win rate      : {m['win_rate']:.1%}  ({m['wins']}W / {m['losses']}L)")
    print(f"    Total P&L     : {tot_s}    avg/trade: ${m['avg_pnl']:+,.2f}")
    win_s = green(f"${m['biggest_win']:+,.2f}")
    loss_s = red(f"${m['biggest_loss']:+,.2f}")
    print(f"    Biggest win   : {win_s}   biggest loss: {loss_s}")
    print(f"    Profit conc.  : {m['profit_concentration']:.1%} of gross profit "
          f"from the single biggest win")
    print(f"    Loss conc.    : {m['loss_concentration']:.1%} of gross loss "
          f"from the single biggest loss")
    print(f"    Premium spent : ${m['premium_spent']:,.2f}   "
          f"return on spend: {m['return_on_spend']:+.1%}")
    print(f"    Max drawdown  : ${m['max_drawdown']:,.2f}   Sharpe: {m['sharpe']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
