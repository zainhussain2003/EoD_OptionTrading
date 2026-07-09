# strategy/thursday-intraday — Thursday intraday, AAPL & TSLA, calls & puts

Finds the best *time frame* to **enter** and the best *time frame* to **exit** an
**AAPL or TSLA option** over the whole regular session (**9:30 AM–4:00 PM ET**),
on **Thursdays only** — a same-day intraday trade in **both directions** (calls
and puts).

This is the **intraday** sibling of `strategies/thursday/` (which buys Thursday
and *holds to Friday*). Here you **buy and sell the same Thursday**.

## The instrument: the Friday weekly, traded intraday on Thursday

AAPL and TSLA don't list Thursday expiries, so the option traded is the
**Friday-expiry weekly** — bought and sold intraday on Thursday, i.e. **1 day to
expiry (1DTE)**. The only exception: when that Friday is a market holiday (e.g.
Good Friday) the weekly expires Thursday, making it a **0DTE** trade that day.
Time-to-expiry in the Black-Scholes fallback counts **trading hours** to the
Friday 4 PM close, so the overnight gap doesn't decay the option as if calendar
time had passed.

## How it works

- **Minute data → time frames.** Per Thursday, every 1-minute close in the
  session is captured; a frame's price is the **mean of its 1-minute closes**
  (noise reduction). A frame is a contiguous window `[start, end]` of arbitrary
  length (5 min → full day), not snapped to 5-minute marks — `12:32–12:45` is
  valid.
- **A trade** enters during the entry frame at `mean(entry)` and exits during the
  exit frame at `mean(exit)`, with `exit_start ≥ entry_end` (exit strictly after
  entry). P&L/share = `mean(exit) − mean(entry)`.
- **Search** is coarse (5-min grid over a duration list) → fine (slide the
  winning boundaries ±5 min at 1-min resolution), scored by
  `win_rate × avg_payoff`.
- **Sizing:** `contracts = ceil(TARGET_SPEND / mean(entry_frame))`, min 1
  (`TARGET_SPEND = 1.00` ⇒ ≥ ~$100 premium/trade).
- A second **outliers-removed** pass drops winning trades over `OUTLIER_MAX` and
  re-optimizes, so a lucky spike can't define the "optimal" frame.

Each of the four legs — **AAPL call, AAPL put, TSLA call, TSLA put** — gets its
own optimal entry/exit frame in `metrics.json → legs`.

## Output contract (consumed by the pipeline)

`strategy.py` is the pipeline entry point. It writes to `STRATEGY_RESULTS_DIR`
(defaults to `./output`):

- `metrics.json` — overall + per-leg optimal frames (**required**)
- `trades.csv` — per-Thursday ledger for every leg at its optimal frames
- `equity_curve.png` — cumulative P&L per leg
- plus the rich `backtest_thursday_intraday_timeframe_*` `.csv`/`.txt`
  (+ `_outliers_removed.txt`) tables per option type

and prints the `===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add ALPACA_API_KEY + ALPACA_SECRET_KEY for real data
python strategy.py            # pipeline artifacts + summary
python backtest_timeframe.py  # full terminal report (heatmaps, top frame pairs)
```

Knobs at the top of `backtest_timeframe.py`:

```python
LOOKBACK_DAYS = 730     # calendar days to test
TARGET_SPEND  = 1.00    # minimum premium per share ($1.00 = ~$100/trade)
OUTLIER_MAX   = 2000    # 2nd pass drops winning trades over $ this
```

## Data source

- **Alpaca Markets** (`alpaca-py`) — real historical 1-minute option bars, used
  when `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are set. **Strongly preferred.**
- **yfinance + Black-Scholes** — automatic fallback reconstructing option prices
  from the underlying's path and realized vol (trading-hours time-to-expiry).

## Layout

```
strategy.py            pipeline adapter — entry point, emits the output contract
backtest_timeframe.py  standalone entry — knobs + sizing/scoring functions
timeframe_engine.py    coarse→fine frame search, heatmaps, tables, CSV/TXT
analysis/backtester.py captures each Thursday's full session (Friday-expiry weekly)
config.py              tickers (AAPL, TSLA), option types (C, P), session window
models.py              dataclasses + data-source tags
utils/date_utils.py    Thursday dates, weekly-expiry roll, NYSE holidays, sessions
utils/math_utils.py    Black-Scholes call & put + realized vol
data/alpaca_fetcher.py real option/stock bars (primary)
data/yf_fetcher.py     yfinance fallback
```

> **Disclaimer:** For research/education. Not financial advice. Past
> performance does not guarantee future results.
