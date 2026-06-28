#!/usr/bin/env python3
"""
EoD Options Trading Probability Analyzer
Systematic MWF ATM call trading: find the optimal entry/exit time, trade every week.

Usage:
  python main.py --backtest              Find optimal buy/sell time from history
  python main.py --backtest --brief      Backtest with a condensed provenance summary
  python main.py --scan                  Show current ATM prices (run at optimal time)
  python main.py --scan --force-run      Show prices anytime (for testing)
  python main.py --log                   Show trade history and P&L

The --backtest output includes a DATA PROVENANCE report showing, per ticker,
exactly which numbers came from real Alpaca option prices vs Black-Scholes
estimates — so you know how much to trust each result. Use --brief to hide the
per-date breakdown and show only the summary.
"""

import argparse
import os
import sys
import time
from datetime import datetime

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_fetcher(args):
    """Return Alpaca fetcher if keys present, else yfinance fallback."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from data.yf_fetcher import YFinanceFetcher

    if ALPACA_AVAILABLE and not args.no_alpaca:
        fetcher = AlpacaFetcher.from_env()
        if fetcher is not None:
            print("  Data source: Alpaca Markets API")
            return fetcher, 'Alpaca'

    print("  Data source: yfinance (set ALPACA_API_KEY for real options data)")
    return YFinanceFetcher(), 'yfinance'


def cmd_backtest(args) -> None:
    from config import Config
    from analysis.backtester import Backtester
    from output.display import (
        print_header, print_backtest_results, print_heatmap,
        print_data_source_report, print_footer,
    )

    config = Config()
    if args.tickers:
        config.tickers = [t.upper() for t in args.tickers]
    if args.days:
        config.backtest_days = args.days

    print_header('backtest')
    fetcher, source = _get_fetcher(args)

    print(f"\nRunning backtest over last {config.backtest_days} calendar days")
    print(f"Testing all 5-minute entry/exit combinations in the 3:00–3:55 PM ET window\n")

    start = time.time()
    backtester = Backtester(fetcher, config)
    results = backtester.run(config.tickers)
    elapsed = time.time() - start

    print_backtest_results(results)

    # Detailed data-provenance report per ticker (real vs simulated prices)
    print(f"\n{'#' * 64}")
    print("#  DATA PROVENANCE  —  where every number came from")
    print(f"{'#' * 64}")
    show_dates = not args.brief
    for result in results:
        print_data_source_report(result, show_dates=show_dates)

    for result in results:
        print_heatmap(result, top_n=10)

    print_footer(len(results), elapsed, source)


def cmd_scan(args) -> None:
    from config import Config
    from analysis.backtester import Backtester
    from data.yf_fetcher import YFinanceFetcher
    from output.display import print_header, print_scan_results, print_footer
    from trade_log.logger import log_scan_targets
    from utils.date_utils import (
        is_mwf, now_et, get_next_mwf_dates, get_atm_strikes,
        detect_strike_interval, minute_to_str
    )

    now = now_et()
    hour = now.hour

    if not args.force_run:
        if not is_mwf():
            print("Today is not a MWF trading day. Use --force-run to override.")
            sys.exit(0)
        if not (15 <= hour < 16):
            print(f"Current time {now.strftime('%I:%M %p ET')} is outside 3–4 PM window.")
            print("Use --force-run to scan anyway.")
            sys.exit(0)

    config = Config()
    if args.tickers:
        config.tickers = [t.upper() for t in args.tickers]

    print_header('scan')
    fetcher, source = _get_fetcher(args)

    # Load backtest optimal times from a saved file, or compute quickly
    # For now, default to 3:15 entry / 3:50 exit (common pattern; override with --entry/--exit)
    entry_minute = args.entry_minute if args.entry_minute else 915  # 3:15 PM
    exit_minute  = args.exit_minute  if args.exit_minute  else 950  # 3:50 PM
    entry_str = minute_to_str(entry_minute)
    exit_str  = minute_to_str(exit_minute)

    print(f"\nScanning at {now.strftime('%I:%M %p ET')}")
    print(f"Target schedule: Buy {entry_str}, Sell {exit_str} (run --backtest to refine)\n")

    start = time.time()
    log_targets = []

    # Find today's MWF expiry
    yf_fetcher = YFinanceFetcher()
    expiry_dates_by_ticker = {}
    for ticker in config.tickers:
        exp_dates = yf_fetcher.get_mwf_expiry_dates(ticker, max_count=1)
        if exp_dates:
            expiry_dates_by_ticker[ticker] = exp_dates[0]

    for ticker in config.tickers:
        try:
            spot = fetcher.fetch_spot_price(ticker)
            expiry = expiry_dates_by_ticker.get(ticker)
            if expiry is None:
                print(f"  {ticker}: Could not find MWF expiry date. Skipping.")
                continue

            # Get the 2 nearest ATM strikes
            interval = detect_strike_interval(spot)
            lower, upper = get_atm_strikes(spot, interval)

            contracts = fetcher.fetch_option_chain(ticker, expiry, config.risk_free_rate)

            # Filter to just our 2 ATM strikes
            atm_contracts = [c for c in contracts if c.strike in (lower, upper)]

            # If chain returned nothing, build minimal display from BS
            if not atm_contracts and isinstance(fetcher, YFinanceFetcher):
                atm_contracts = _fallback_contracts(ticker, spot, lower, upper, expiry, config)

            atm_contracts.sort(key=lambda c: c.strike)
            print_scan_results(ticker, spot, atm_contracts, entry_str, exit_str)

            for c in atm_contracts:
                log_targets.append((ticker, c))

        except Exception as e:
            print(f"  {ticker}: Error — {e}")
            continue

        time.sleep(0.5)

    if log_targets and not args.no_log:
        log_scan_targets(log_targets, entry_str, exit_str, config.trades_csv)
        print(f"  Logged {len(log_targets)} contracts to {config.trades_csv}")

    elapsed = time.time() - start
    print_footer(len(config.tickers), elapsed, source)


def _fallback_contracts(ticker, spot, lower, upper, expiry, config):
    """Construct minimal OptionContract objects via Black-Scholes when no chain data."""
    from datetime import datetime
    from models import OptionContract
    from utils.date_utils import compute_T, ET
    from utils.math_utils import black_scholes_call, calc_theta_hourly

    sigma = {'AAPL': 0.25, 'NVDA': 0.55, 'TSLA': 0.65, 'MSFT': 0.22}.get(ticker, 0.35)
    now_dt = datetime.now(ET)
    contracts = []

    for strike in (lower, upper):
        T = compute_T(expiry, now_dt)
        price, delta, _, _ = black_scholes_call(spot, strike, T, config.risk_free_rate, sigma)
        theta_h = calc_theta_hourly(spot, strike, T, config.risk_free_rate, sigma)
        contracts.append(OptionContract(
            ticker=ticker,
            contract_symbol='',
            strike=strike,
            expiry=expiry,
            bid=round(price * 0.95, 2),
            ask=round(price * 1.05, 2),
            mid_price=round(price, 2),
            volume=0,
            open_interest=0,
            implied_volatility=sigma,
            delta=delta,
            theta_hourly=theta_h,
            in_the_money=(strike < spot),
        ))
    return contracts


def cmd_log(args) -> None:
    from config import Config
    from trade_log.reporter import print_report

    config = Config()
    print_report(config.trades_csv)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='EoD Options Analyzer — systematic MWF ATM call trading'
    )
    sub = p.add_subparsers(dest='mode')

    # --backtest
    bt = sub.add_parser('--backtest', help='Find optimal entry/exit time from history')
    bt.add_argument('--tickers', nargs='+', help='Override default tickers')
    bt.add_argument('--days', type=int, default=60, help='Days to look back (default 60)')
    bt.add_argument('--no-alpaca', action='store_true')

    # --scan
    sc = sub.add_parser('--scan', help='Show current ATM prices at the optimal time')
    sc.add_argument('--force-run', action='store_true', help='Run outside 3-4 PM / non-MWF day')
    sc.add_argument('--tickers', nargs='+')
    sc.add_argument('--entry-minute', type=int, default=0, dest='entry_minute')
    sc.add_argument('--exit-minute',  type=int, default=0, dest='exit_minute')
    sc.add_argument('--no-log', action='store_true', help='Do not write to trades.csv')
    sc.add_argument('--no-alpaca', action='store_true')

    # --log
    lg = sub.add_parser('--log', help='Show trade history and P&L')

    return p


# Allow the subcommand flags to also work as the first positional arg
# e.g. `python main.py --backtest` (without sub-parser confusion)
def _normalize_argv() -> list[str]:
    argv = sys.argv[1:]
    if argv and argv[0] in ('--backtest', '--scan', '--log'):
        return argv
    return argv


def main() -> None:
    sys.argv = [sys.argv[0]] + _normalize_argv()

    # Manual dispatch so --backtest / --scan / --log work as top-level flags
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    mode = sys.argv[1]

    class Args:
        tickers = None
        days = 60
        force_run = False
        entry_minute = 0
        exit_minute = 0
        no_log = False
        no_alpaca = False
        brief = False

    args = Args()

    # Parse remaining flags
    rest = sys.argv[2:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == '--tickers':
            args.tickers = []
            i += 1
            while i < len(rest) and not rest[i].startswith('--'):
                args.tickers.append(rest[i])
                i += 1
        elif tok == '--days' and i + 1 < len(rest):
            args.days = int(rest[i + 1])
            i += 2
        elif tok == '--force-run':
            args.force_run = True
            i += 1
        elif tok == '--entry-minute' and i + 1 < len(rest):
            args.entry_minute = int(rest[i + 1])
            i += 2
        elif tok == '--exit-minute' and i + 1 < len(rest):
            args.exit_minute = int(rest[i + 1])
            i += 2
        elif tok == '--no-log':
            args.no_log = True
            i += 1
        elif tok == '--no-alpaca':
            args.no_alpaca = True
            i += 1
        elif tok == '--brief':
            args.brief = True
            i += 1
        else:
            i += 1

    if mode == '--backtest':
        cmd_backtest(args)
    elif mode == '--scan':
        cmd_scan(args)
    elif mode == '--log':
        cmd_log(args)
    else:
        print(f"Unknown mode: {mode}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
