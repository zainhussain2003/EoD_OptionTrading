# strategy/friday_intraday_concentration_capped — Friday 0DTE intraday, concentration-capped

Same study as `strategies/friday_intraday/` — the best intraday **entry frame**
and **exit frame** for a **0DTE Friday-expiry** option over the full 9:30 AM–4:00
PM ET session, on Fridays, calls and puts, across seven large-cap names:

> **TSLA · AMZN · AAPL · NVDA · GOOGL · MSFT · ORCL**

— but with a different way of deciding the "best" frame: a **single-transaction
concentration cap** replaces the old fixed-dollar outlier removal.

## Why the concentration cap (vs. the $2,000 outlier drop)

The old approach dropped any winning trade over a fixed **$2,000** and re-ran.
That's the wrong yardstick: a $2,000 day inside a **$10,000** total is only **20%**
— and big swings are normal and *expected* with options, so there's no reason to
throw it out. What actually tells you a window is fragile is when **one** trade
carries most of the result.

So instead we ask: **is any single transaction more than 51% of the total P&L?**

```
single_trade_share = (largest single winning trade P&L) / (net total P&L)
eligible  ⇔  net_total_pnl > 0  AND  single_trade_share <= MAX_SINGLE_TRADE_SHARE  (0.51)
```

- A $2,000 top trade out of $10,000 total → **20%** → fine, keep the frame.
- A $5,100 top trade out of $10,000 total → **51%** → borderline / disqualified:
  the window is likely luck-driven and unlikely to repeat.

No trade is ever removed. The cap only decides **which frame may be chosen**, so
the P&L you read is the real, whole P&L — you're just refusing to crown a frame
that only looks good because of one jackpot print. This mirrors
`strategies/mwf-concentration-capped/`.

## Two passes

| Pass | Eligibility | Answers |
|------|-------------|---------|
| **1 — unconstrained** | any frame with enough samples | the naive "best" frame |
| **2 — concentration-capped** | `single_trade_share ≤ 51%` | the best frame whose edge isn't one-trade luck |

Ranking metric is unchanged (`win_rate × avg_payoff`); the cap only filters
eligibility in pass 2. Comparing the two passes per leg shows whether the edge
holds up or collapses once no single trade may dominate.

There is **no `OUTLIER_MAX`** and no winning-trade dollar-drop pass.

## Output contract

`strategy.py` writes to `STRATEGY_RESULTS_DIR` (default `./output`):

- `metrics.json` — pass-1 aggregates + per-leg frames (each with its
  `single_trade_share`), and a nested `concentration_capped` block for pass 2
  (**required**)
- `trades.csv` (pass 1) and `trades_concentration_capped.csv` (pass 2)
- `equity_curve.png` — cumulative P&L per leg
- rich `backtest_friday_intraday_concentration_capped_<ticker>_<type>_*`
  `.csv`/`.txt` (+ `_concentration_capped.txt`) tables per ticker × option type

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
LOOKBACK_DAYS          = 730     # calendar days to test
TARGET_SPEND           = 1.00    # minimum premium per share ($1.00 = ~$100/trade)
MAX_SINGLE_TRADE_SHARE = 0.51    # pass 2: biggest single win <= this × total P&L
```

> Seven tickers × two option types = 14 independent frame searches per run, so a
> full-history run is heavier than a single-ticker study — expect a longer Forge
> step on the runner.

## Data source

- **Alpaca Markets** (`alpaca-py`) — real historical 1-minute option bars, used
  when `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are set. **Strongly preferred.**
- **yfinance + Black-Scholes** — automatic fallback reconstructing 0DTE option
  prices from the underlying's path and realized vol.

## Layout

```
strategy.py            pipeline adapter — entry point, emits the output contract
backtest_timeframe.py  standalone entry — knobs, sizing/scoring, cap eligibility
timeframe_engine.py    coarse→fine frame search; pass 2 applies the concentration cap
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
