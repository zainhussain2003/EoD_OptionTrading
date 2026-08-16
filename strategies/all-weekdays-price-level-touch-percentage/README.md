# All-Weekday Price-Level-Touch Analysis (Percentage)

For a basket of tickers — each evaluated at several **percentage move thresholds**
on **all five weekdays** — this study measures how often the scan day touches a
price level defined relative to the **prior trading day's near-close price**, at
any point during the regular session (**9:30 AM–4:00 PM ET**).

| Scan day | Baseline (prior trading day) | Gap |
|----------|------------------------------|-----|
| Monday    | prior **Friday** 3:50–3:55 PM | 3 calendar days |
| Tuesday   | prior **Monday** 3:50–3:55 PM | 1 day |
| Wednesday | prior **Tuesday** 3:50–3:55 PM | 1 day |
| Thursday  | prior **Wednesday** 3:50–3:55 PM | 1 day |
| Friday    | prior **Thursday** 3:50–3:55 PM | 1 day |

## What this changes vs. the Mon/Wed/Fri run

Built the **v2 way** (`mon-wed-fri-price-level-touch-percentage-v2`) — TSLA + AAPL
on a dense percentage ladder — not the original 5-ticker / 5-level study. Two
changes:

| | v2 (Mon/Wed/Fri) | this run |
|---|---|---|
| Tickers | TSLA, AAPL | TSLA, AAPL *(unchanged)* |
| Scan days | Mon / Wed / Fri (3) | **Mon / Tue / Wed / Thu / Fri (5)** |
| Thresholds | 0.5 → 5% (11) | **0.5 → 15% (14)** — adds 7%, 10%, 15% |
| Lookback | 730 days, rolling | 730 days, rolling *(unchanged)* |
| Baseline | prior day 3:50–3:55 PM | *(unchanged)* |

**Tuesday and Thursday** complete the week. Only Monday's baseline crosses a
weekend; Tue/Wed/Thu/Fri all use a 1-trading-day gap, so those four are directly
comparable to each other — the v2 run could only ever compare two such days
(Wed vs Fri).

**7% / 10% / 15%** fix a real defect in v2. That ladder stopped at 5%, which
**right-censored** every larger move: a session past 5% was recorded as just "5%"
no matter how much further it went. AAPL on 2026-07-31 fell **9.84%** and was
logged as 5% — understated by 4.84pp — and 3 of 99 AAPL Fridays exceeded the cap.
The true magnitude always survived in `max_*_swing_pct`, but the **hit-rate curve**
(the view you'd use to pick a level) went artificially flat at the bottom because
the ladder stopped, not because the risk did.

Adding rungs is **purely additive** — it cannot change any existing level's hit
rate — so every v2 number remains directly comparable. Observed maxima over the v2
window were ~12% (TSLA down), ~9.8% (AAPL down) and 24.8% (TSLA up), so 15%
captures nearly everything; read `max_*_swing_pct` for the rare move beyond it.

Because the 730-day window is **rolling**, it slides forward to the run date
rather than extending over the previous run.

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
  percentage `pct` on the ladder (0.5% → 15%):
  - `touched_up`   = session high `≥ R × (1 + pct)`
  - `touched_down` = session low  `≤ R × (1 − pct)`

  Using the intraday high/low (not the close) captures a level that is *reached*
  at any point in the day, even intrabar. Each ticker × day gets **one hit-rate
  sub-table per percentage**.
- **Swings.** For every session, the full **max-up swing** (`high − R`) and
  **max-down swing** (`R − low`) — the biggest move each way that day — are
  recorded from each baseline, reported as a **percentage of `R` with the dollar
  move in brackets** (e.g. `+2.34% ($8.96)`). The swing distance does not depend on
  the threshold, so it is shown once per day.
- **Steadiest baseline.** Each single reference minute is ranked by its **average
  absolute deviation from the per-session 3:50–55 mean** (lower = steadier). The
  steadiest minute is recommended per ticker **per day**; all six are still shown.
- **Day comparison.** After the five day blocks, each ticker gets a combined
  **day-comparison table** that puts the Mon / Tue / Wed / Thu / Fri averages
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

Per ticker (printed in a bold-bordered block and saved to a `.txt`), the five scan
days are reported one after another, then summarized together:

- **Per scan day (Monday → Tuesday → Wednesday → Thursday → Friday):**
  - **Hit-rate sub-tables — one per percentage (14 of them, 0.5% → 15%)** — per
    reference time: sessions analyzed, +pct hits, −pct hits, both, neither (%).
  - **Swing table** (once per day, since swings don't depend on the threshold) —
    average and largest max-up / max-down swing as a **percentage of the reference
    with the dollar move in brackets**. The `max` columns report the **biggest
    single-day percentage swing** in each direction.
  - **Steadiest-baseline ranking** + the recommended reference minute for that day.
- **Day comparison** — all five weekday averages together, one row per percentage.

Files written to `backtest_results/` (standalone) or `STRATEGY_RESULTS_DIR`
(pipeline):

| File | Contents |
|------|----------|
| `level_touch_<ticker>_<lookback>days_<stamp>.txt` | Per-ticker report: five day blocks + the day-comparison table. |
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
