# Weekly Move Probability (Friday → next-Friday)

For a basket of tickers — **TSLA, AAPL, NVDA, ORCL, MSFT** — using **stock prices
only (no options)**, this study measures the probability that, **one week later at
Friday's close**, the price has:

- moved **up ≥ +1.5%**,
- moved **down ≤ −1.5%**, or
- stayed **within the ±1.5% band** (the remainder).

The three probabilities **sum to 100%** by construction (this is a *terminal*,
close-to-close measurement). Both the **±1.5% threshold** and the **date range
(lookback days)** are parameters.

This is a **stock price-level** study — there are **no options and no P&L**. It
reuses the data-fetching infrastructure of the `calls/` / `puts/` backtests and
the `friday-price-level-touch*` studies (`data/`, `utils/`, `models.py`); only the
measurement is new.

## How it works

- **Reference price (both legs).** For a given Friday, the price is the **average
  of the 1-minute *close* prices over the 3:50–4:00 PM ET window** — the ten bars
  3:50, 3:51, … 3:59 (the 4:00 PM bar is excluded). We use the **close** of each
  bar, not VWAP.
- **Holiday rule.** If a Friday is a market holiday / closed (no usable 3:50–4:00
  window), the leg steps back to the **prior Thursday's** 3:50–4:00 window (then
  Wed, Tue …) and the week is flagged as a fallback. Applied to **both** the entry
  and exit legs.
- **Pairing.** Entry = each Friday's reference; exit = the **following Friday's**
  reference (exactly one week / 7 calendar days later). Non-consecutive pairs are
  never measured as a single week.
- **Weekly return.** `(exit_ref / entry_ref) − 1`.
- **Bucketing.**
  - `up`   if return **≥ +threshold**  (default +1.5%)
  - `down` if return **≤ −threshold**  (default −1.5%)
  - `flat` otherwise (inside the ±band)
- **Dropped weeks.** A week is **dropped, never silently filled**, if either leg
  lacks a usable reference even after the Thursday step-back; the reason is logged.

## Configuration

Edit `config.py` (or the constants at the top of `backtest_weekly_move.py`):

| Setting | Default | Meaning |
|---------|---------|---------|
| `tickers` | TSLA, AAPL, NVDA, ORCL, MSFT | universe |
| `threshold` | `0.015` | the ±band (up/down/flat) |
| `backtest_days` | `730` | lookback window in calendar days (~2 years) |
| `ref_start_minute` / `ref_end_minute` | `950` / `960` | 3:50–4:00 PM ET window |
| `max_baseline_lookback` | `4` | how far back to step on a Friday holiday |

## Running

```bash
# Full terminal report + backtest_results/ artifacts
python backtest_weekly_move.py

# Pipeline-contract run (metrics.json, weekly_log.csv, probabilities.png, JSON block)
python strategy.py
```

Stock bars come from **Alpaca** when `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are
set, otherwise from **yfinance**. Note: yfinance only serves ~30 days of minute
history, so a long lookback (730 days) requires Alpaca.

## Outputs

Per-ticker and pooled:

- **`metrics.json`** (required) — `p_up`, `p_down`, `p_flat`, week counts, and
  mean / median / stdev of weekly returns, per ticker and pooled.
- **`weekly_log.csv`** — per-week ledger: ticker, entry date, entry ref, exit
  date, exit ref, return %, bucket, the actual reference dates used, and
  entry/exit Thursday-fallback flags.
- **`probability_summary_*.csv`** — per-ticker + pooled summary table.
- **`weekly_move_<ticker>_*.txt`** — rich per-ticker report incl. the per-week log
  and any dropped weeks.
- **`probabilities.png`** — grouped up/flat/down probability bars per ticker + pooled.

## Output contract

`strategy.py` is the pipeline entry point and emits the standard contract:
`metrics.json` (with `status`), the fixed-name `weekly_log.csv`, `probabilities.png`,
and the `===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` stdout block. On failure
it writes `metrics.json` with `status:"error"` and exits non-zero.
