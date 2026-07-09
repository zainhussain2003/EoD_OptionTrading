# strategy/friday_intraday — Friday intraday 0DTE, 7 names, calls & puts

Finds the best *time frame* to **enter** and the best *time frame* to **exit** a
**0DTE Friday-expiry option** over the whole regular session
(**9:30 AM–4:00 PM ET**), on **Fridays only** — a same-day intraday trade in
**both directions** (calls and puts), across seven large-cap names:

> **TSLA · AMZN · AAPL · NVDA · GOOGL · MSFT · ORCL**

It is the multi-ticker generalization of `strategies/tsla-friday-timeframe/`, and
the Friday counterpart to `strategies/thursday-intraday/` (which trades the
Friday weekly intraday one day early, on Thursday).

## The instrument: the Friday weekly, traded intraday on Friday (0DTE)

You buy and sell the **same Friday**, trading that day's expiring weekly — so the
option is **0DTE**. When a Friday is a market holiday, the backtester falls back
to the preceding **Thursday's** real data/expiry so no week is dropped and the
week stays on real prices (never a simulated phantom Friday).

## How it works

- **Minute data → time frames.** Per Friday, every 1-minute close in the session
  is captured; a frame's price is the **mean of its 1-minute closes** (noise
  reduction). A frame is a contiguous window `[start, end]` of arbitrary length
  (5 min → full day), not snapped to 5-minute marks — `12:32–12:45` is valid.
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

Each leg — one per **ticker × call/put** (14 in all) — gets its own optimal
entry/exit frame in `metrics.json → legs`, keyed e.g. `NVDA_CALL`, `ORCL_PUT`.

## Output contract (consumed by the pipeline)

`strategy.py` is the pipeline entry point. It writes to `STRATEGY_RESULTS_DIR`
(defaults to `./output`):

- `metrics.json` — overall + per-leg optimal frames (**required**)
- `trades.csv` — per-Friday ledger for every leg at its optimal frames
- `equity_curve.png` — cumulative P&L per leg
- plus the rich `backtest_friday_intraday_timeframe_*` `.csv`/`.txt`
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

> Seven tickers × two option types = 14 independent frame searches per run, so a
> full-history run is meaningfully heavier than the single-ticker study — expect
> a longer Forge step on the runner.

## Data source

- **Alpaca Markets** (`alpaca-py`) — real historical 1-minute option bars, used
  when `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are set. **Strongly preferred.**
- **yfinance + Black-Scholes** — automatic fallback reconstructing 0DTE option
  prices from the underlying's path and realized vol.

## Layout

```
strategy.py            pipeline adapter — entry point, emits the output contract
backtest_timeframe.py  standalone entry — knobs + sizing/scoring functions
timeframe_engine.py    coarse→fine frame search, heatmaps, tables, CSV/TXT
analysis/backtester.py captures each Friday's full session (0DTE weekly)
config.py              tickers (7 names), option types (C, P), session window
models.py              dataclasses + data-source tags
utils/date_utils.py    Friday dates, sessions, ATM strikes, OCC symbols
utils/math_utils.py    Black-Scholes call & put + realized vol
data/alpaca_fetcher.py real option/stock bars (primary)
data/yf_fetcher.py     yfinance fallback
```

> **Disclaimer:** For research/education. Not financial advice. Past
> performance does not guarantee future results.
