# Friday Price-Level-Touch Analysis (Percentage)

For a basket of tickers — each evaluated at several **percentage move thresholds**
— this study measures how often **Friday** touches a price level defined relative
to **Thursday's near-close price**, at any point during the regular session
(**9:30 AM–4:00 PM ET**).

This is the **percentage** variant of `friday-price-level-touch`: instead of one
fixed-dollar threshold per ticker, every ticker is tested at **±2%, ±2.5% and
±3%** of the reference price, so the move is volatility-normalized and directly
comparable across names.

| Ticker | Thresholds |
|--------|------------|
| TSLA   | ±2% · ±2.5% · ±3% |
| AAPL   | ±2% · ±2.5% · ±3% |
| NVDA   | ±2% · ±2.5% · ±3% |
| MSFT   | ±2% · ±2.5% · ±3% |
| ORCL   | ±2% · ±2.5% · ±3% |

Each ticker's percentage list is independently editable in `config.py`
(`ticker_pcts`). This is a **stock price-level** study — there are **no options
and no P&L**. It reuses the data-fetching and reporting infrastructure of the
`calls/` / `puts/` backtests and the `tsla-friday-timeframe` study, but the
analysis is a level-touch / swing count, not an option backtest.

## How it works

- **Thursday baseline (captured minute-by-minute).** Rather than a single 4:00
  close, the preceding Thursday's price is read at **3:50, 3:51, 3:52, 3:53, 3:54
  and 3:55 PM** ET (the close of each 1-minute bar), plus a **3:50–55 average**
  baseline. Capturing the range lets us compare which near-close minute is the
  steadiest reference. If Thursday is a market holiday, the baseline steps back to
  the nearest preceding trading day (Wed, Tue …) and the substitution is noted.
- **Friday scan.** Every 1-minute bar from 9:30 AM to 4:00 PM is fetched; the
  session **high** (max of bar highs) and **low** (min of bar lows) are taken.
- **Touch detection (intraday high/low).** For each Thursday reference price `R`
  and each percentage `pct` (2%, 2.5%, 3%):
  - `touched_up`   = Friday session high `≥ R × (1 + pct)`
  - `touched_down` = Friday session low  `≤ R × (1 − pct)`

  Using the intraday high/low (not the close) captures a level that is *reached*
  at any point in the day, even intrabar. Each ticker gets **one hit-rate
  sub-table per percentage**.
- **Swings.** For every Friday, the full **max-up swing** (`fri_high − R`) and
  **max-down swing** (`R − fri_low`) — the biggest move each way that day — are
  recorded from each baseline, reported as a **percentage of `R` with the dollar
  move in brackets** (e.g. `+2.34% ($8.96)`). The swing distance is the same for
  all three thresholds (it doesn't depend on `pct`), so it is shown once per
  ticker.
- **Steadiest baseline.** Each single reference minute is ranked by its **average
  absolute deviation from the per-Friday 3:50–55 mean** (lower = steadier). The
  steadiest minute is recommended per ticker; all six are still shown.

`target_spend` ($1.00) and `outlier_max` ($2,000) are option-template parameters
with **no effect** in this study; they are carried only to document the requested
run parameters.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add ALPACA_API_KEY + ALPACA_SECRET_KEY
```

Data source priority:
- **Alpaca Markets** (`alpaca-py`) — real historical 1-minute **stock** bars. Used
  when keys are present.
- **yfinance** — automatic fallback (still real stock prices; this study never
  simulates, since it uses no options).

## Usage

```bash
python backtest_level_touch.py      # full terminal report + CSV/TXT artifacts
python strategy.py                  # also emits the pipeline contract files
```

Change `LOOKBACK_DAYS` at the top of `backtest_level_touch.py` to widen/narrow the
window (default **730** calendar days). Edit `config.py` (`ticker_pcts`) to change
the percentage thresholds per ticker, the Thursday reference minutes, or the
Friday scan window.

## Output

For each ticker (printed in a bold-bordered block and saved to a `.txt`):

- **Hit-rate sub-tables — one per percentage (2%, 2.5%, 3%)** — per reference
  time: Fridays analyzed, +pct hits, −pct hits, both, neither (with percentages).
- **Swing table** (shown once per ticker, since swings don't depend on the
  threshold) — per reference time: average and largest max-up / max-down swing
  from that baseline, as a **percentage of the reference with the dollar move in
  brackets**. The `max` columns report the **biggest single-day percentage swing**
  in each direction.
- **Steadiest-baseline ranking** + the recommended Thursday reference minute.

Files written to `backtest_results/` (standalone) or `STRATEGY_RESULTS_DIR`
(pipeline):

| File | Contents |
|------|----------|
| `level_touch_<ticker>_<lookback>days_<stamp>.txt` | Per-ticker report (per-pct hit-rate sub-tables + swing table). |
| `touch_summary_<lookback>days_<stamp>.csv` | Combined hit-rate + swing table, one row per ticker × pct × reference. |
| `swings_<lookback>days_<stamp>.csv` | Per-Friday × per-reference × pct swing ledger (tidy/long), with swing %. |
| `metrics.json` | Machine-readable contract metrics (pipeline); hit rates nested under each pct, swings separate. |
| `swings.csv` | Fixed-name copy of the swing ledger (pipeline). |
| `hit_rates.png` | +/− touch-rate bars, one row per ticker × one column per pct (optional). |

## Pipeline contract

`strategy.py` honors the EoD pipeline contract: reads `ALPACA_API_KEY` /
`ALPACA_SECRET_KEY` from env, writes everything to `STRATEGY_RESULTS_DIR`
(defaulting to `./output`), writes `metrics.json`, prints the
`===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block, and exits 0 on success or
writes `metrics.json` with `status:"error"` and exits 1 on failure.
