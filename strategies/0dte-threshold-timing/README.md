# 0DTE / short-dated option threshold-timing study

A **descriptive** historical study (no live trading, no orders). For each long
option — call **and** put — in the Mag-7 + ORCL + AMD universe, it measures over
historical minute quotes **when** the mark reaches a ladder of profit thresholds
(+20 … +100 %) and **how long** that exit window stays open, producing an
entry/exit playbook per symbol, direction, expiry regime, entry-time window and
moneyness.

## What it computes, per trade instance (one contract, one entry minute)
- `first_hit[T]` — minutes from entry to the FIRST time the mark reaches +T %
- `last_hold[T]` — minutes from entry to the LAST time it was still ≥ +T %
- `mfe_pct / mfe_min` — peak favorable excursion and when
- `mae_pct / mae_min` — worst adverse excursion and when

Threshold ladder T (%): 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100.

## Fill modes (both, side by side)
- `mid` — mark = (bid+ask)/2, entry at mid. The optimistic ceiling.
- `market` — open at ask, close at bid (long-option realism). `pct[t] = bid[t]/ask[entry] − 1`.
  Every trade starts ≈ −spread %. **This is the number to trust.**

Sanity invariant (asserted per instance): a `market` hit implies a `mid` hit, and
where both hit, `market` first-touch ≥ `mid` first-touch.

## Three analysis modes
- **Mode A — base-rate surface.** The 5-min entry sweep (09:35–15:30 ET) analyzed
  as independent what-ifs. Feeds the bucketed tables and the optimal-entry ranking.
- **Mode B — sequential non-overlapping schedule (HINDSIGHT).** Greedy first-touch
  exit; counts clean, non-overlapping +T % moves per day. **Opportunity counting,
  not a live rule** — labelled as such everywhere.
- **Mode C — walk-forward forced-exit strategy (tradeable).** Entry schedule is
  ranked on TRAIN only (by hit-probability of +T %), frozen, and applied to TEST;
  exit at first-touch of +T % or forced-exit at `MAX_EXIT_TIME` (default session
  close). Non-hit/forced-exit trades are **kept** (dropping them fakes an edge).
  Reports out-of-sample expectancy on `market` fills.

## Data
Real **top-of-book option quotes** from Alpaca (bid/ask resampled to the minute
close) via `data/alpaca_quotes.py`, discovering expiries empirically. Without
Alpaca credentials it falls back to a clearly-labelled **SIMULATED** (Black-Scholes)
frame so the pipeline never goes silent — those numbers are **not a real edge**.
Expiry cadence and moneyness (ITM/ATM/OTM1/OTM2+) are detected from the data.

## Deliverables (under `STRATEGY_RESULTS_DIR`)
```
metrics.json                              # pipeline contract (required)
analysis/output/threshold_by_symbol/<SYM>.csv
analysis/output/optimal_entry.csv         # targets 30/50/75/100 %, ranked by market hit%
analysis/output/dow_rollup.csv
analysis/output/summary.md                # top findings + validation report
analysis/output/run_config.json           # universe, dates, detected cadence, counts
sequential/<SYM>_trades.csv               # Mode B trades (HINDSIGHT)
sequential/<SYM>_daily.csv                # Mode B per-day
sequential/<SYM>_strategy_trades.csv      # Mode C trades (walk-forward)
sequential/<SYM>_strategy_perf.csv        # Mode C out-of-sample performance
```

## Run
```
python strategy.py          # ./output; SIMULATED without keys, real quotes with them
python tests/test_core.py   # offline unit tests (no network)
```
Processes one symbol at a time to bound memory. Uses `python` (Windows target).

## Layout
```
config.py                 all knobs (universe, thresholds, sweep, walk-forward, columns)
strategy.py               pipeline entry point / orchestration
data/schema.py            data contract + adapter + SIMULATED fallback
data/alpaca_quotes.py     Alpaca historical option-quotes adapter
core/threshold_timing.py  analyze_trade (first_hit/last_hold/mfe/mae, fill modes)
core/expiry.py            empirical expiry + regime (0DTE vs bridge)
core/moneyness.py         ITM/ATM/OTM1/OTM2+ classification
core/sweep.py             entry sweep → Mode A surface
core/aggregate.py         bucketed base-rate tables + DOW roll-up
core/optimizer.py         entry-window ranker (hit-probability of +T%)
core/sequential.py        Mode B
core/walkforward.py       Mode C
core/validation.py        adversarial review
core/report.py            summary.md
```
