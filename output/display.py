import os
import sys
from datetime import datetime

from models import (
    BacktestResult, BacktestPairResult, OptionContract,
    SOURCE_REAL, SOURCE_SIM, SOURCE_NO_STOCK,
)
from utils.date_utils import minute_to_str, now_et, ET


def _ansi(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(t: str) -> str: return _ansi(t, '32')
def _red(t: str) -> str:   return _ansi(t, '31')
def _yellow(t: str) -> str: return _ansi(t, '33')
def _bold(t: str) -> str:   return _ansi(t, '1')
def _cyan(t: str) -> str:   return _ansi(t, '36')


def print_header(mode: str = '') -> None:
    now = now_et()
    time_str = now.strftime('%I:%M %p ET')
    # Hours until 4 PM
    close_et = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now < close_et:
        h_left = (close_et - now).total_seconds() / 3600
        time_left = f"{h_left:.2f}h to close"
    else:
        time_left = "market closed"

    w = 64
    title = f"  EoD Options Analyzer  |  {time_str}  |  {time_left}"
    print(_bold('=' * w))
    print(_bold(f"{title:<{w}}"))
    print(_bold('=' * w))


def _source_tag(primary: str) -> str:
    """Short colored tag for a result's primary data source."""
    if primary == 'REAL':
        return _green('REAL')
    if primary == 'SIMULATED':
        return _yellow('SIM')
    if primary == 'MIXED':
        return _yellow('MIXED')
    return _red('NONE')


def print_backtest_results(results: list[BacktestResult]) -> None:
    n_dates = results[0].n_dates if results else 0
    print(f"\n{_bold('=== BACKTEST RESULTS')} ({n_dates} past MWF dates analyzed)\n")

    header = f"  {'Ticker':<8} {'Best Entry':>11} {'Best Exit':>10} {'Win Rate':>9} {'Avg Payoff':>11} {'Score':>7} {'Dates':>6} {'Source':>7}"
    sep    = f"  {'-'*8} {'-'*11} {'-'*10} {'-'*9} {'-'*11} {'-'*7} {'-'*6} {'-'*7}"
    print(header)
    print(sep)

    for r in results:
        entry_str = minute_to_str(r.best_entry_minute)
        exit_str  = minute_to_str(r.best_exit_minute)
        win_pct   = f"{r.win_rate:.1%}"
        payoff    = f"${r.avg_payoff:+.3f}"
        score     = f"{r.score:.4f}"
        n         = str(r.n_dates)
        src       = _source_tag(r.primary_source)
        # pad the source tag accounting for invisible ANSI codes
        src_pad = src + ' ' * max(0, 7 - len(r.primary_source[:5] if r.primary_source != 'SIMULATED' else 'SIM'))

        base = f"  {r.ticker:<8} {entry_str:>11} {exit_str:>10} {win_pct:>9} {payoff:>11} {score:>7} {n:>6} "
        if r.win_rate >= 0.60:
            print(_green(base) + src)
        elif r.win_rate >= 0.50:
            print(_yellow(base) + src)
        else:
            print(base + src)

    print()
    print(_bold("RECOMMENDATION: Trade every MWF using the entry/exit times above."))
    print(f"  {_green('REAL')} = backed by actual Alpaca option prices  |  "
          f"{_yellow('SIM')} = Black-Scholes estimate  |  {_red('NONE')} = no data")
    print()


def print_data_source_report(result: BacktestResult, show_dates: bool = True) -> None:
    """Detailed provenance for one ticker: exactly where every number came from.

    Makes it obvious whether the backtest is trustworthy (real option prices)
    or approximate (Black-Scholes simulation when real bars weren't available).
    """
    w = 64
    print(_bold('=' * w))
    print(_bold(f"  DATA SOURCE REPORT — {result.ticker}"))
    print(_bold('=' * w))

    total_pulls = result.n_real_pulls + result.n_sim_pulls
    real_pct = (result.n_real_pulls / total_pulls * 100) if total_pulls else 0.0
    sim_pct  = (result.n_sim_pulls / total_pulls * 100) if total_pulls else 0.0

    # Headline verdict
    if result.primary_source == 'REAL':
        verdict = _green("✓ ACCURATE — every data point is a real Alpaca option price")
    elif result.primary_source == 'SIMULATED':
        verdict = _yellow("≈ APPROXIMATE — all prices are Black-Scholes estimates "
                          "(no real option bars were available)")
    elif result.primary_source == 'MIXED':
        verdict = _yellow(f"◑ MIXED — {real_pct:.0f}% real prices, {sim_pct:.0f}% "
                          "Black-Scholes estimates")
    else:
        verdict = _red("✗ NO DATA — no usable stock or option bars were returned")
    print(f"  Verdict: {verdict}")
    print()

    # Counts
    print(f"  {'Real Alpaca option-bar pulls':<38}: {_green(str(result.n_real_pulls)):>4}  ({real_pct:.0f}%)")
    print(f"  {'Black-Scholes simulated pulls':<38}: {_yellow(str(result.n_sim_pulls)):>4}  ({sim_pct:.0f}%)")
    print(f"  {'MWF dates skipped (no stock bars)':<38}: {result.n_skipped_dates:>4}")
    print(f"  {'Dates successfully used':<38}: {result.n_dates:>4}")
    print(f"  {'Total payoff samples in stats':<38}: {result.n_total_samples:>4}")
    if result.n_sim_pulls > 0:
        print(f"  {'Volatility (σ) used for simulation':<38}: {result.sim_sigma:>6.1%}")
    print()

    # Per-date breakdown
    if show_dates and result.pull_details:
        print(f"  Per-date detail (each MWF tries 2 ATM strikes):")
        print(f"  {'Date':<12} {'Strike':>8} {'Contract':<22} {'Bars':>5} {'Spot':>8}  Source")
        print(f"  {'-'*12} {'-'*8} {'-'*22} {'-'*5} {'-'*8}  {'-'*24}")
        for d in result.pull_details:
            if d.source == SOURCE_REAL:
                src = _green('REAL  (Alpaca option bars)')
            elif d.source == SOURCE_SIM:
                src = _yellow('SIM   (Black-Scholes)')
            else:
                src = _red('SKIP  (no stock bars)')
            strike_s = f"{d.strike:.1f}" if d.strike else "—"
            spot_s = f"${d.spot_at_3pm:.2f}" if d.spot_at_3pm else "—"
            contract_s = d.contract_symbol or "—"
            print(f"  {d.date:<12} {strike_s:>8} {contract_s:<22} {d.n_bars:>5} {spot_s:>8}  {src}")
        print()
    print(_bold('=' * w))
    print()


def print_heatmap(result: BacktestResult, top_n: int = 10) -> None:
    """Print top-N entry/exit pairs as a ranked table + compact heatmap."""
    if not result.all_pairs:
        print(f"  No heatmap data for {result.ticker}.")
        return

    print(f"\n  {_bold(result.ticker)} — Top {min(top_n, len(result.all_pairs))} entry/exit combinations:")
    print(f"  {'Rank':>5} {'Entry':>9} {'Exit':>9} {'Win%':>7} {'Avg P&L':>9} {'N':>5}")
    print(f"  {'-'*5} {'-'*9} {'-'*9} {'-'*7} {'-'*9} {'-'*5}")

    for i, pair in enumerate(result.all_pairs[:top_n]):
        rank = i + 1
        entry_s = minute_to_str(pair.entry_minute)
        exit_s  = minute_to_str(pair.exit_minute)
        win_p   = f"{pair.win_rate:.1%}"
        avg_p   = f"${pair.avg_payoff:+.3f}"
        n       = str(pair.n_trades)

        marker = " ★" if rank == 1 else "  "
        if pair.win_rate >= 0.60:
            line = _green(f"  {rank:>5} {entry_s:>9} {exit_s:>9} {win_p:>7} {avg_p:>9} {n:>5}{marker}")
        elif pair.win_rate >= 0.50:
            line = _yellow(f"  {rank:>5} {entry_s:>9} {exit_s:>9} {win_p:>7} {avg_p:>9} {n:>5}{marker}")
        else:
            line = f"  {rank:>5} {entry_s:>9} {exit_s:>9} {win_p:>7} {avg_p:>9} {n:>5}{marker}"
        print(line)

    # Mini ASCII heatmap of win rates
    _print_win_heatmap(result)


def _print_win_heatmap(result: BacktestResult) -> None:
    """ASCII grid: entry times (rows) × exit times (cols), cell = win%."""
    pair_map: dict[tuple, float] = {}
    for p in result.all_pairs:
        pair_map[(p.entry_minute, p.exit_minute)] = p.win_rate

    entries = sorted(set(p.entry_minute for p in result.all_pairs))
    exits   = sorted(set(p.exit_minute   for p in result.all_pairs))

    # Show at most 10 entry × 10 exit to keep display compact
    entries = entries[:10]
    exits   = exits[:10]

    cell_w = 6
    print(f"\n  {_bold(result.ticker)} win-rate heatmap (entry ↓  exit →)\n")

    # Header row
    header = f"  {'Entry':>7} |"
    for ex in exits:
        ex_s = minute_to_str(ex).replace(' PM', '').replace(' AM', '')
        header += f" {ex_s:>{cell_w}}"
    print(header)
    print(f"  {'-'*7}-+" + '-' * (cell_w + 1) * len(exits))

    for en in entries:
        en_s = minute_to_str(en).replace(' PM', '').replace(' AM', '')
        row = f"  {en_s:>7} |"
        for ex in exits:
            if ex <= en:
                row += f" {'---':>{cell_w}}"
            elif (en, ex) in pair_map:
                wr = pair_map[(en, ex)]
                cell = f"{wr:.0%}"
                if wr >= 0.60:
                    row += f" {_green(f'{cell:>{cell_w}}')}"
                elif wr >= 0.50:
                    row += f" {_yellow(f'{cell:>{cell_w}}')}"
                else:
                    row += f" {cell:>{cell_w}}"
            else:
                row += f" {'':>{cell_w}}"
        print(row)
    print()


def print_scan_results(ticker: str, spot: float,
                        contracts: list[OptionContract],
                        best_entry_str: str, best_exit_str: str) -> None:
    print(f"\n  {_bold(ticker)}  ${spot:.2f}  — ATM calls expiring today (MWF 0DTE)")
    print(f"  Backtest optimal: Buy {_green(best_entry_str)}, Sell {_green(best_exit_str)}")
    print()
    print(f"  {'Strike':>8}  {'Bid':>6}  {'Ask':>6}  {'Mid':>6}  {'IV%':>6}  {'Delta':>7}  {'Theta/Hr':>9}")
    print(f"  {'-'*8}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*9}")

    for c in contracts:
        iv_pct = f"{c.implied_volatility * 100:.1f}%"
        theta_s = f"${c.theta_hourly:+.3f}"
        itm_marker = " ITM" if c.in_the_money else "    "
        print(f"  {c.strike:>8.2f}  {c.bid:>6.2f}  {c.ask:>6.2f}  "
              f"{c.mid_price:>6.2f}  {iv_pct:>6}  {c.delta:>7.3f}  {theta_s:>9}{itm_marker}")
    print()


def print_footer(n_tickers: int, elapsed: float, data_source: str) -> None:
    w = 64
    print('=' * w)
    print(f"  {n_tickers} ticker(s) analyzed in {elapsed:.1f}s  |  Data: {data_source}")
    print(f"  {_red('WARNING: Not financial advice. Past performance ≠ future results.')}")
    print('=' * w)
