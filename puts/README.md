# EoD_OptionTrading

Systematic end-of-day (3–4 PM ET) **put option** trading for MWF (Monday/
Wednesday/Friday) 0DTE expiries on **AAPL, NVDA, TSLA, MSFT**.

The idea is **not** discretionary signals. The system backtests every
`(entry_time, exit_time)` combination inside the 3–4 PM window across all past
MWF dates, finds the pair with the highest probability of profit, and you then
trade that **fixed schedule every MWF** — e.g. _"buy the ATM AAPL put at
3:15 PM, sell at 3:50 PM."_

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add ALPACA_API_KEY + ALPACA_API_SECRET
```

Data source priority:
- **Alpaca Markets** (`alpaca-py`) — real historical option bars + live chains
  with market greeks. Used when keys are present.
- **yfinance** — automatic fallback (options reconstructed via Black-Scholes).

## Usage

```bash
python main.py --backtest             # find the optimal buy/sell time per ticker
python main.py --scan                 # show current ATM strikes (run 3-4 PM on a MWF)
python main.py --scan --force-run     # show prices anytime (testing)
python main.py --log                  # cumulative P&L from your trade log
```

`--backtest` prints, per ticker: the optimal entry/exit time, win rate, average
payoff, and a full entry×exit win-rate heatmap.

### Data provenance (real vs simulated)

Every `--backtest` run includes a **DATA PROVENANCE** report so you know how
much to trust each result. For each ticker it shows a verdict — `REAL`
(actual Alpaca option prices), `SIMULATED` (Black-Scholes estimates when real
option bars weren't available), `MIXED`, or `NONE` — plus counts, the
volatility used for any simulation, and a per-date table listing the exact
contract, number of bars, spot price, and source for every data pull. Add
`--brief` to show only the summary without the per-date table.

## Testing

A full test suite validates the math, dates, parsing, backtester payoff logic,
the trade logger, **and live Alpaca data pulls**.

```bash
python run_tests.py            # everything (offline + live Alpaca)
python run_tests.py --offline  # logic only, no network needed
python run_tests.py --live     # only the live Alpaca data-pull tests
```

- **Offline tests** run anywhere and check Black-Scholes against textbook
  reference values, OCC symbol formatting, DST-aware time handling, and verify
  the backtester's win-rate/payoff arithmetic against hand-computed synthetic
  price series.
- **Live tests** pull real spot prices, option chains, and historical option
  bars from Alpaca to confirm formatting and that backtest inputs are accurate.
  They **skip with a clear reason** (not fail) if credentials, network, or
  options entitlement are missing — so run them locally, not in a sandbox.

The runner prints a clear ✓/✗ per check with a section-by-section tally and a
final pass/fail banner.

## Project Layout

```
main.py              CLI: --backtest | --scan | --log
config.py            tickers, risk-free rate, window settings
models.py            OptionContract, BacktestResult, TradeRecord
utils/               Black-Scholes math, MWF dates, OCC symbols
data/                alpaca_fetcher (primary) + yf_fetcher (fallback)
analysis/backtester  core: optimal entry/exit finder
trade_log/           CSV logger + P&L reporter
output/display       tables + heatmap rendering
tests/               offline + live test modules
run_tests.py         test runner
```

> **Disclaimer:** For research/education. Not financial advice. Past
> probabilities do not guarantee future results.
