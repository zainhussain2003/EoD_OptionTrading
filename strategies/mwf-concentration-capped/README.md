# MWF Concentration-Capped Schedules (TSLA & AAPL, calls + puts)

Finds, for each **(ticker, weekday, option type)**, the best fixed 5-minute
`(entry_time, exit_time)` schedule to trade a 0DTE ATM option — ranked by
`win_rate × avg_payoff` (max expected profit), exactly like the by-day *sized*
backtests — but only among schedules that survive a **single-transaction
concentration cap**.

## The concentration cap (replaces the old outlier system)

A schedule is only **eligible** to be chosen as the "best" timeframe if no single
winning trade dominates its total return over the lookback:

```
single_trade_share = (largest single winning trade P&L) / (net total P&L)
eligible  ⇔  net_total_pnl > 0  AND  single_trade_share <= MAX_SINGLE_TRADE_SHARE
```

- **Example.** A 3:30–3:50 PM schedule that made **$1,000** total but where one
  trade made **$600** has a share of **60% > 51%** → disqualified: that window is
  luck-driven, not statistically best. A schedule whose biggest win is **$300 of
  $1,000 (30%)** is fine.
- If `net_total_pnl <= 0` the schedule is ineligible (share undefined). A schedule
  with **no winning trade** is ineligible.
- The cap only decides **eligibility**. The ranking metric
  (`win_rate × avg_payoff`) is unchanged.
- There is **no outlier system**: no `OUTLIER_MAX`, no winning-trade dollar-drop
  pass. The largest single win and the total are taken from the **same sized
  dollar P&L** used everywhere else, so the share is a true share of the real
  total.

## Knobs (top of `backtest_concentration.py`)

| Knob | Default | Meaning |
|------|---------|---------|
| `MAX_SINGLE_TRADE_SHARE` | `0.51` | Biggest single winning trade may be at most ~50% (±1%) of net total P&L. |
| `TARGET_SPEND` | `1.00` | Minimum premium per share (`contracts = ceil(TARGET_SPEND / entry_price)`, min 1) — ~$100 per trade. |

## Scope (see `config.py`)

| Day | Lookback | Window (ET) | Notes |
|-----|----------|-------------|-------|
| Monday | 140 days | 3:00–4:00 PM | |
| Wednesday | 140 days | 3:00–4:00 PM | |
| Friday | 730 days | 2:00–4:00 PM | Thursday fallback for closed sessions |

Tickers: **TSLA, AAPL**. Option types: **calls and puts**. Data: Alpaca paper +
market-data, read-only; falls back to Black-Scholes simulation when option bars
are unavailable.

## Files

| File | Role |
|------|------|
| `config.py` | Tickers, option types, and the per-day `DaySpec` (lookback + window). |
| `analysis/backtester.py` | Captures ATM call & put minute prices per MWF date, keyed by `(ticker, opt_type, day_name)`. |
| `concentration_engine.py` | Compact schedule engine. `compute_pair_stats` retains each schedule's **largest single winning trade** so the cap can compute `single_trade_share`. |
| `backtest_concentration.py` | Driver with the knobs at the top; defines `size_fn`, `score_key`, and the cap eligibility, and orchestrates the run. |
| `strategy.py` | Pipeline adapter — emits `metrics.json`, `trades.csv`, `equity_curve.png`, `concentration_report.txt`, and the `===STRATEGY_SUMMARY_JSON===` block. |

## Output contract

`strategy.py` writes to `STRATEGY_RESULTS_DIR` (default `./output`):

- **`metrics.json`** (required) — overall aggregates plus a `combos` map reporting,
  per `(ticker, day, opt_type)`: the chosen `entry_time`/`exit_time`, `win_rate`,
  `total_pnl`, and the winning `single_trade_share` of the chosen schedule (so
  it's visible the cap held).
- `trades.csv` — per-day ledger across every combo.
- `equity_curve.png` — cumulative P&L, one line per combo.
- `concentration_report.txt` — the full plain-text terminal report.

## Running

```bash
python backtest_concentration.py   # terminal report only
python strategy.py                 # + the pipeline artifacts
```
