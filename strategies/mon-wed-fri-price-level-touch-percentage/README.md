# Mon/Wed/Fri Price-Level-Touch Analysis (Percentage)

For a basket of tickers — each evaluated at several **percentage move thresholds**
on **three scan days (Monday, Wednesday, Friday)** — this study measures how often
the scan day touches a price level defined relative to the **prior trading day's
near-close price**, at any point during the regular session (**9:30 AM–4:00 PM
ET**).

It is the multi-day extension of `friday-price-level-touch-percentage`: same five
percentage thresholds and five tickers, but run for Monday, Wednesday and Friday,
each against the close of the trading day immediately before it.

| Scan day | Baseline (prior trading day) |
|----------|------------------------------|
| Monday    | prior **Friday** 3:50–3:55 PM |
| Wednesday | prior **Tuesday** 3:50–3:55 PM |
| Friday    | prior **Thursday** 3:50–3:55 PM |

Every ticker is tested at **±1%, ±1.5%, ±2%, ±2.5% and ±3%** of the baseline price,
so the move is volatility-normalized and directly comparable across names and days.
The percentage list and the scan-day list are independently editable in `config.py`
(`ticker_pcts`, `scan_days`).

This is a **stock price-level** study — there are **no options and no P&L**. It
reuses the data-fetching and reporting infrastructure of the `calls/` / `puts/`
backtests, but the analysis is a level-touch / swing count, not an option backtest.

## How it works

- **Baseline (captured minute-by-minute).** For each scan day, the prior trading
  day's price is read at **3:50, 3:51, 3:52, 3:53, 3:54 and 3:55 PM** ET (the close
  of each 1-minute bar), plus a **3:50–55 average** baseline. Monday steps back
  over the weekend to the prior Friday; if that day is a market holiday, the
  baseline steps back further to the nearest preceding trading day and the
  substitution is noted.
- **Scan.** Every 1-minute bar from 9:30 AM to 4:00 PM on the scan day is fetched;
  the session **high** (max of bar highs) and **low** (min of bar lows) are taken.
- **Touch detection (intraday high/low).** For each baseline price `R` and each
  percentage `pct` (1%, 1.5%, 2%, 2.5%, 3%):
  - `touched_up`   = session high `≥ R × (1 + pct)`
  - `touched_down` = session low  `≤ R × (1 − pct)`

  Using the intraday high/low (not the close) captures a level that is *reached*
  at any point in the day, even intrabar. Each ticker × day gets **one hit-rate
  sub-table per percentage**.
- **Swings.** For every session, the full **max-up swing** (`high − R`) and
  **max-down swing** (`R − low`) — the biggest move each way that day — are
  recorded from each baseline, reported as a **percentage of `R` with the dollar
  move in brackets** (e.g. `+2.34% ($8.96)`). The swing distance is the same for
  all five thresholds, so it is shown once per day.
- **Steadiest baseline.** Each single reference minute is ranked by its **average
  absolute deviation from the per-session 3:50–55 mean** (lower = steadier). The
  steadiest minute is recommended per ticker **per day**; all six are still shown.
- **Day comparison.** After the three day blocks, each ticker gets a combined
  **day-comparison table** that puts the Monday / Wednesday / Friday averages
  (up% / down% / neither% at each day's recommended baseline, plus average swing)
  side by side, so the days are easy to read against each other.

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
window (default **730** calendar days). Edit `config.py` to change the percentage
thresholds per ticker (`ticker_pcts`), the scan days (`scan_days`), the baseline
reference minutes, or the scan session window.

## Output

Per ticker (printed in a bold-bordered block and saved to a `.txt`), the three scan
days are reported one after another, then summarized together:

- **Per scan day (Monday → Wednesday → Friday):**
  - **Hit-rate sub-tables — one per percentage (1%, 1.5%, 2%, 2.5%, 3%)** — per
    reference time: sessions analyzed, +pct hits, −pct hits, both, neither (%).
  - **Swing table** (once per day, since swings don't depend on the threshold) —
    average and largest max-up / max-down swing as a **percentage of the reference
    with the dollar move in brackets**. The `max` columns report the **biggest
    single-day percentage swing** in each direction.
  - **Steadiest-baseline ranking** + the recommended reference minute for that day.
- **Day comparison** — the Mon/Wed/Fri averages together, one row per percentage.

Files written to `backtest_results/` (standalone) or `STRATEGY_RESULTS_DIR`
(pipeline):

| File | Contents |
|------|----------|
| `level_touch_<ticker>_<lookback>days_<stamp>.txt` | Per-ticker report: three day blocks + the day-comparison table. |
| `touch_summary_<lookback>days_<stamp>.csv` | Combined hit-rate + swing table, one row per ticker × day × pct × reference. |
| `swings_<lookback>days_<stamp>.csv` | Per-session × per-reference × pct swing ledger (tidy/long), with a `day` column and swing %. |
| `metrics.json` | Machine-readable contract metrics; hit rates nested under each ticker → day → pct, swings per day. |
| `swings.csv` | Fixed-name copy of the swing ledger (pipeline). |
| `hit_rates.png` | Touch-rate bars, one row per ticker × one column per scan day (optional). |

## Pipeline contract

`strategy.py` honors the EoD pipeline contract: reads `ALPACA_API_KEY` /
`ALPACA_SECRET_KEY` from env, writes everything to `STRATEGY_RESULTS_DIR`
(defaulting to `./output`), writes `metrics.json`, prints the
`===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block, and exits 0 on success or
writes `metrics.json` with `status:"error"` and exits 1 on failure.
