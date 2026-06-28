# Friday Price-Level-Touch Analysis

For a basket of tickers — each with its own **dollar move threshold** — this study
measures how often **Friday** touches a price level defined relative to
**Thursday's near-close price**, at any point during the regular session
(**9:30 AM–4:00 PM ET**).

| Ticker | Threshold |
|--------|-----------|
| TSLA   | ±$8  |
| AAPL   | ±$6  |
| NVDA   | ±$5  |
| MSFT   | ±$10 |
| ORCL   | ±$7  |

This is a **stock price-level** study — there are **no options and no P&L**. It
reuses the data-fetching and reporting infrastructure of the `calls/` / `puts/`
backtests and the `tsla-friday-timeframe` study, but the analysis is a level-touch
/ swing count, not an option backtest.

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
  and the ticker's threshold:
  - `touched_up`   = Friday session high `≥ R + threshold`
  - `touched_down` = Friday session low  `≤ R − threshold`

  Using the intraday high/low (not the close) captures a level that is *reached*
  at any point in the day, even intrabar.
- **Swings.** For every Friday, the full **max-up swing** (`fri_high − R`) and
  **max-down swing** (`R − fri_low`) are recorded from each baseline — the real
  distance travelled, not just whether the threshold was hit.
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
window (default **730** calendar days). Edit `config.py` to change the ticker
thresholds, the Thursday reference minutes, or the Friday scan window.

## Output

For each ticker (printed in a bold-bordered block and saved to a `.txt`):

- **Hit-rate table** — per reference time: Fridays analyzed, +threshold hits,
  −threshold hits, both, neither (with percentages).
- **Swing table** — per reference time: average and largest max-up / max-down
  swing from that baseline.
- **Steadiest-baseline ranking** + the recommended Thursday reference minute.

Files written to `backtest_results/` (standalone) or `STRATEGY_RESULTS_DIR`
(pipeline):

| File | Contents |
|------|----------|
| `level_touch_<ticker>_<lookback>days_<stamp>.txt` | Per-ticker report. |
| `touch_summary_<lookback>days_<stamp>.csv` | Combined hit-rate + swing table, all tickers. |
| `swings_<lookback>days_<stamp>.csv` | Per-Friday × per-reference swing ledger (tidy/long). |
| `metrics.json` | Machine-readable contract metrics (pipeline). |
| `swings.csv` | Fixed-name copy of the swing ledger (pipeline). |
| `hit_rates.png` | +/− touch-rate bars per reference time (optional). |

## Pipeline contract

`strategy.py` honors the EoD pipeline contract: reads `ALPACA_API_KEY` /
`ALPACA_SECRET_KEY` from env, writes everything to `STRATEGY_RESULTS_DIR`
(defaulting to `./output`), writes `metrics.json`, prints the
`===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block, and exits 0 on success or
writes `metrics.json` with `status:"error"` and exits 1 on failure.
