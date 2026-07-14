# strategy/intraday — all weekdays intraday, one run

Every weekday as its own same-session (buy & sell that day) intraday time-frame
study, in **one place** — best entry window + exit window per **(day, equity,
call/put)** over the full 9:30 AM–4:00 PM ET session.

| Day | Entry | Expiry | DTE | Lookback | Tickers |
|-----|-------|--------|-----|----------|---------|
| **Monday** | Monday | Monday | 0DTE | 150 d | Mag7 − META (6) |
| **Tuesday** | Tuesday | Wednesday | 1DTE | 150 d | Mag7 − META (6) |
| **Wednesday** | Wednesday | Wednesday | 0DTE | 150 d | Mag7 − META (6) |
| **Thursday** | Thursday | Friday | 1DTE | 730 d | Mag7 − META + AMD + ORCL (8) |
| **Friday** | Friday | Friday | 0DTE | 730 d | Mag7 − META + AMD + ORCL (8) |

- **Mag 7 − META** = `AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA`.
- **Thursday & Friday** additionally include `AMD, ORCL`.
- All of this lives in [`config.py → DAY_SPECS`](config.py); change it there.

## How it works

For each day the driver builds a `Config` (tickers, entry weekday, expiry
weekday, lookback) and runs the shared time-frame engine:

- **Minute data → frames.** Per session, every 1-minute close is captured; a
  frame's price is the **mean of its 1-minute closes**. A frame is any contiguous
  `[start, end]` window (5 min → full day).
- **A trade** enters during the entry frame at `mean(entry)` and exits during the
  exit frame at `mean(exit)`, with `exit_start ≥ entry_end`.
- **Search:** coarse 5-min grid → 1-min refine, scored by `win_rate × avg_payoff`.
- **Sizing:** `contracts = ceil(TARGET_SPEND / mean(entry_frame))`, min 1.
- **Expiry:** the option expiring on the day's `expiry_weekday` in the same week
  (0DTE when it equals the entry day, else 1DTE); a holiday expiry rolls back one
  trading day.

Each **(day, ticker, call/put)** leg is keyed e.g. `NVDA_CALL` inside its day.

## Data source

Real **Alpaca** option bars when the given expiry contract exists, otherwise a
**Black-Scholes** fallback. The Mag 7 do carry Monday/Wednesday-expiry contracts
for recent dates (so those come back largely real), but coverage thins going back
— every leg and day reports its own `data_source` (REAL / MIXED / SIM).

## Output contract

`strategy.py` writes to `STRATEGY_RESULTS_DIR` (default `./output`):

- **`metrics.json`** — a `days` map (Monday … Friday), each with its expiry,
  lookback, tickers, aggregate stats, and per-leg optimal frames; plus a
  `portfolio` rollup across all days (**required**).
- `trades.csv` — combined per-session ledger, with a **`day`** column tagging each row.
- `equity_curve.png` — cumulative P&L, one line per weekday.
- rich `backtest_intraday_<day>_<ticker>_<type>_*` `.csv`/`.txt` tables.

and prints the `===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add ALPACA_API_KEY + ALPACA_SECRET_KEY for real data
python strategy.py            # all five days + day-keyed metrics
python backtest_timeframe.py  # full per-day terminal report (heatmaps, top pairs)
```

Knob at the top of `backtest_timeframe.py`: `TARGET_SPEND = 1.00`. Everything
else (per-day expiry / lookback / tickers) is in `config.DAY_SPECS`.

> **Runtime note:** this is five studies in one — the Thursday and Friday passes
> are 730-day × 8-ticker each, so a full run is the heaviest in the repo. Expect a
> long Forge step on the runner.

## Layout

```
strategy.py            pipeline adapter — drives all 5 days, emits day-keyed metrics
backtest_timeframe.py  standalone entry — loops DAY_SPECS + sizing/scoring
timeframe_engine.py    day-agnostic coarse→fine frame search (takes a Config)
analysis/backtester.py captures a session by config.entry_weekday / expiry_weekday
config.py              DAY_SPECS (per-day expiry/lookback/tickers) + Config
models.py              dataclasses + data-source tags
utils/date_utils.py    weekday date generator, generic expiry_for, NYSE holidays
utils/math_utils.py    Black-Scholes call & put + realized vol
data/alpaca_fetcher.py real option/stock bars (primary)
data/yf_fetcher.py     yfinance fallback
```

> **Disclaimer:** For research/education. Not financial advice. Past
> performance does not guarantee future results.
