# strategy/thursday — Thursday → Friday, AAPL & TSLA, calls **and** puts

Answers: **on Thursday, what is the best time to buy — and when to sell — an
AAPL or TSLA weekly option that expires Friday?** It studies both directions:

- **CALL** (bet the stock rises) — strike **at or above** spot.
- **PUT** (bet the stock falls) — strike **at or below** spot.

for **AAPL** and **TSLA**, so you get all four legs (AAPL call, AAPL put,
TSLA call, TSLA put) in one run.

## The trade being modelled

| Step | Rule |
|------|------|
| **Buy** | The trading day **before** expiry — normally **Thursday** — between **3:55 and 3:59 PM ET** (one row per minute, so we can find the best entry minute). |
| **Watch** | The exact contract, all of the **expiry day** (Friday), 9:30 AM–4:00 PM ET. |
| **Sell** | Rest a **limit at the return target**. If it hasn't filled by **3:55 PM ET** on the expiry day, sell at 3:55 PM at the market. |

**Holiday roll (no week skipped, stays on real data):** the weekly expiry is
Friday, so you normally buy Thursday. When that Friday is a market holiday (e.g.
Good Friday) the option expires **Thursday** instead, so the entry rolls back to
**Wednesday**:

| Week | Buy (entry) | Expiry / tracked day |
|------|-------------|----------------------|
| Normal | **Thursday** 3:55–3:59 PM | Friday |
| Friday closed | **Wednesday** 3:55–3:59 PM | Thursday |

## Return targets (profit ÷ premium paid)

`target_price = entry_price × (1 + multiple)`, so a $0.50 entry:

| Multiple | Price target | $0.50 entry → |
|----------|--------------|---------------|
| 1.0x | ×2.00 | **$1.00** (double) |
| 1.5x | ×2.50 | $1.25 |
| 2.0x | ×3.00 | $1.50 |
| 2.5x | ×3.50 | $1.75 |

## What "best time to buy and sell" means here

For every leg (ticker × call/put) the engine measures the
**limit-at-target-else-sell-3:55** strategy for **every** entry minute
(3:55–3:59) × **every** target, then reports the single **(entry minute,
target)** combo that nets the most **$ per $100 staked** — that is the leg's
recommended buy time and profit target. `metrics.json → legs` carries that
recommendation, its win/fill rates, and the touch probability for each leg.

## Output contract (consumed by the pipeline)

`strategy.py` is the pipeline entry point. It writes to `STRATEGY_RESULTS_DIR`
(defaults to `./output`):

- `metrics.json` — overall + per-leg metrics (**required**)
- `trades.csv` — per-weekly-pair ledger for each leg at its best config
- `equity_curve.png` — cumulative P&L per leg
- plus the rich `thu_fri_aapl_tsla_*.{csv,txt}` full tables

and prints the `===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add ALPACA_API_KEY + ALPACA_SECRET_KEY for real data
python strategy.py
```

Two knobs at the top of `strategy.py`:

```python
LOOKBACK_DAYS    = 365                     # calendar days of history to test
RETURN_MULTIPLES = [1.0, 1.5, 2.0, 2.5]    # profit targets (× premium paid)
```

## Data source

- **Alpaca Markets** (`alpaca-py`) — real historical option bars, used when
  `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are set. **Strongly preferred.**
- **yfinance + Black-Scholes** — automatic fallback that reconstructs option
  prices from the underlying's path and realized vol. A call's option-high is
  driven by the stock's **high**, a put's by the stock's **low**. Both legs of
  every sample share one source, so the return ratio is never real-vs-simulated.

## Layout

```
strategy.py           pipeline adapter — entry point, emits the output contract
thu_fri_engine.py     engine: Thu→Fri pairing, call+put sampling, stats, tables
config.py             tickers (AAPL, TSLA), option types (C, P), risk-free rate
models.py             dataclasses + data-source tags
utils/date_utils.py   Thu→Fri pairing, sessions, OCC symbols, strike selection
utils/math_utils.py   Black-Scholes call & put + realized vol
data/alpaca_fetcher.py real option/stock bars (primary)
data/yf_fetcher.py     yfinance fallback
```

> **Disclaimer:** For research/education. Not financial advice. Past
> probabilities do not guarantee future results.
