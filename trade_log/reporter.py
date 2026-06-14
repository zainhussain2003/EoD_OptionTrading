import csv
import os
from collections import defaultdict


def load_trades(csv_path: str = 'trades.csv') -> list[dict]:
    if not os.path.isfile(csv_path):
        return []
    rows = []
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row['premium_paid'] = float(row.get('premium_paid', 0) or 0)
                row['exit_price'] = float(row.get('exit_price', 0) or 0)
                row['payoff'] = float(row.get('payoff', 0) or 0)
                row['profitable'] = str(row.get('profitable', '')).lower() == 'true'
                rows.append(row)
            except Exception:
                continue
    return rows


def print_report(csv_path: str = 'trades.csv') -> None:
    trades = load_trades(csv_path)

    if not trades:
        print("\nNo trades logged yet. Run --scan during the optimal window to log trades.")
        return

    # Per-ticker stats
    ticker_payoffs: dict[str, list] = defaultdict(list)
    for t in trades:
        if t['payoff'] != 0:
            ticker_payoffs[t['ticker']].append(t['payoff'])

    all_payoffs = [t['payoff'] for t in trades if t['payoff'] != 0]
    total_trades = len(all_payoffs)
    wins = sum(1 for p in all_payoffs if p > 0)
    win_rate = wins / total_trades if total_trades else 0.0
    total_pnl = sum(all_payoffs)
    avg_pnl = total_pnl / total_trades if total_trades else 0.0

    # Cumulative growth assuming $100 notional per contract (100 shares)
    cumulative = 0.0
    equity_points = []
    for t in sorted(trades, key=lambda x: (x['date'], x['entry_time'])):
        if t['payoff'] != 0:
            cumulative += t['payoff'] * 100  # per contract (100 shares)
            equity_points.append((t['date'], cumulative))

    w = 60
    sep = '=' * w
    print(f"\n{sep}")
    print(f"{'  TRADE LOG REPORT':^{w}}")
    print(sep)
    print(f"  Total trades logged : {len(trades)}")
    print(f"  Trades with outcome : {total_trades}")
    print(f"  Win rate            : {win_rate:.1%}")
    print(f"  Avg payoff/contract : ${avg_pnl:+.2f}")
    print(f"  Total P&L (×100)    : ${total_pnl * 100:+.2f}")
    print(sep)

    if ticker_payoffs:
        print(f"\n  {'Ticker':<8} {'Trades':>7} {'Wins':>6} {'Win%':>7} {'Avg P&L':>10}")
        print(f"  {'-'*8} {'-'*7} {'-'*6} {'-'*7} {'-'*10}")
        for ticker in sorted(ticker_payoffs):
            plist = ticker_payoffs[ticker]
            tw = sum(1 for p in plist if p > 0)
            ta = sum(plist) / len(plist)
            print(f"  {ticker:<8} {len(plist):>7} {tw:>6} {tw/len(plist):>7.1%} {ta:>+10.2f}")

    if equity_points:
        print(f"\n  Cumulative P&L (per-contract, $100 notional):")
        print(f"  {'Date':<12}  {'Cumulative':>12}")
        print(f"  {'-'*12}  {'-'*12}")
        for d, eq in equity_points[-10:]:  # last 10
            print(f"  {d:<12}  ${eq:>+11.2f}")

    print(f"\n{sep}")
    print("  NOTE: 'payoff' column must be filled in after each trade for P&L tracking.")
    print(f"  Trade log file: {csv_path}")
    print(sep)
