# strategy/tuesday_intraday — Tuesday intraday, Mag 7, calls & puts

Finds the best *time frame* to **enter** and to **exit** a **Magnificent-7**
option over the whole regular session (**9:30 AM–4:00 PM ET**), on **Tuesdays
only** — a same-day intraday trade in **both directions** (calls and puts).

> **AAPL · MSFT · GOOGL · AMZN · NVDA · META · TSLA**

It is the Tuesday counterpart of `strategies/thursday-intraday/`: buy and sell the
**same Tuesday**.

## The instrument: the Wednesday-expiry option, traded intraday on Tuesday (1DTE)

You buy and sell the same **Tuesday**, trading the **Wednesday-expiry** option —
i.e. **1 day to expiry (1DTE)**. If a Wednesday is a market holiday the expiry
rolls back to the Tuesday itself (0DTE).

⚠️ **Data caveat:** individual equities (unlike SPY/QQQ) usually list only
**Friday** weeklies — a real **Wednesday-expiry** contract often does **not**
exist for the Mag 7. When no real Wednesday-expiry option bars are available for a
given Tuesday, the backtest falls back to a **Black-Scholes simulation** (1DTE,
trading-hours time-to-expiry). Real Alpaca option bars are used whenever they
exist; expect these results to lean **simulated**. `metrics.json`'s `data_source`
tells you which.

## How it works

- **Minute data → time frames.** Per Tuesday, every 1-minute close is captured; a
  frame's price is the **mean of its 1-minute closes** (noise reduction). A frame
  is a contiguous window `[start, end]` of arbitrary length (5 min → full day),
  not snapped to 5-minute marks — `12:32–12:45` is valid.
- **A trade** enters during the entry frame at `mean(entry)` and exits during the
  exit frame at `mean(exit)`, with `exit_start ≥ entry_end`. P&L/share =
  `mean(exit) − mean(entry)`.
- **Search** is coarse (5-min grid over a duration list) → fine (slide the winning
  boundaries ±5 min at 1-min resolution), scored by `win_rate × avg_payoff`.
- **Sizing:** `contracts = ceil(TARGET_SPEND / mean(entry_frame))`, min 1.
- A second **outliers-removed** pass drops winning trades over `OUTLIER_MAX` and
  re-optimizes, so a lucky spike can't define the "optimal" frame.

Each leg — one per **ticker × call/put** (14 in all) — gets its own optimal
entry/exit frame in `metrics.json → legs`, keyed e.g. `NVDA_CALL`, `META_PUT`.

## Output contract

`strategy.py` writes to `STRATEGY_RESULTS_DIR` (default `./output`):

- `metrics.json` — overall + per-leg optimal frames (**required**)
- `trades.csv` — per-Tuesday ledger for every leg at its optimal frames
- `equity_curve.png` — cumulative P&L per leg
- rich `backtest_tuesday_intraday_timeframe_<ticker>_<type>_*` `.csv`/`.txt`
  (+ `_outliers_removed.txt`) tables per ticker × option type

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
LOOKBACK_DAYS = 150     # calendar days to test (~21 Tuesdays)
TARGET_SPEND  = 1.00    # minimum premium per share ($1.00 = ~$100/trade)
OUTLIER_MAX   = 2000    # 2nd pass drops winning trades over $ this
```

## Layout

```
strategy.py            pipeline adapter — entry point, emits the output contract
backtest_timeframe.py  standalone entry — knobs + sizing/scoring functions
timeframe_engine.py    coarse→fine frame search, heatmaps, tables, CSV/TXT
analysis/backtester.py captures each Tuesday's full session (Wednesday-expiry option)
config.py              tickers (Mag 7), option types (C, P), session window
models.py              dataclasses + data-source tags
utils/date_utils.py    Tuesday dates, Wednesday-expiry roll, NYSE holidays, sessions
utils/math_utils.py    Black-Scholes call & put + realized vol
data/alpaca_fetcher.py real option/stock bars (primary)
data/yf_fetcher.py     yfinance fallback
```

> **Disclaimer:** For research/education. Not financial advice. Past
> performance does not guarantee future results.
