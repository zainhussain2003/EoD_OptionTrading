# TSLA Friday — Optimal Entry/Exit Time-Frame Analysis

Finds the best *time frame* to **enter** and the best *time frame* to **exit** a
**TSLA 0DTE option** over the whole regular session (**9:30 AM–4:00 PM ET**), on
**Fridays only**, for **both calls and puts**.

Unlike the narrow-window backtests in `calls/` and `puts/` (which test fixed
5-minute entry/exit points inside a one-hour window), this study works over the
entire trading day and searches for *time frames* — each a contiguous window
`[start, end]` of **arbitrary length** (5 minutes up to the full day). Frames are
**not** snapped to clean 5-minute marks: `12:32–12:45` is a valid frame.

You then trade that **fixed schedule every Friday** — e.g. _"buy the ATM TSLA
call somewhere in the 12:32–12:45 PM frame, sell somewhere in the 2:08–2:19 PM
frame."_

## How it works

- **Minute data → time frames.** Per Friday, every 1-minute close in the session
  is fetched, then a frame's price is the **mean of its 1-minute closes** — so
  grouping minutes into frames *reduces noise* instead of chasing single ticks.
- **A trade** enters during the entry frame at `mean(entry)` and exits during the
  exit frame at `mean(exit)`, with the exit frame starting at/after the entry
  frame ends. `P&L/share = mean(exit) − mean(entry)`.
- **Position sizing** (same as `backtest_friday_sized.py`):
  `contracts = ceil(TARGET_SPEND / mean(entry_frame))`, min 1. With
  `TARGET_SPEND = 1.00` that is a minimum of ~$100 premium per trade.
- **Scoring:** frame pairs are ranked by `win_rate × avg_payoff`.
- **Two-stage coarse→fine search** (this is the only structural change from the
  narrow-window engine):
  1. **Coarse** — frame boundaries on a 5-minute grid over a duration list
     spanning 5 minutes to the full day; per-Friday prefix sums make each frame
     mean O(1).
  2. **Fine** — the winning frames' four boundaries are slid ±5 min at **1-minute**
     resolution and re-scored, so the result lands on odd boundaries like
     `12:32–12:47`.
- **Outliers removed pass:** every frame pair is re-scored with its winning
  trades over `OUTLIER_MAX` ($2,000) dropped, then re-optimized — shown below the
  normal output and saved to a separate file.
- **0DTE ATM** strike is chosen from the spot at the open; a Friday with no data
  (market closed) falls back to the preceding **Thursday's** real weekly, never
  simulated. When real option bars are missing, prices fall back to Black-Scholes.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add ALPACA_API_KEY + ALPACA_SECRET_KEY
```

Data source priority:
- **Alpaca Markets** (`alpaca-py`) — real historical 1-minute option bars. Used
  when keys are present.
- **yfinance** — automatic fallback (options reconstructed via Black-Scholes;
  no historical option bars, so expect SIMULATED results without Alpaca keys).

## Usage

```bash
python backtest_timeframe.py
```

This runs both calls and puts in one go. For each option type it prints the
optimal entry/exit frames, a per-Friday P&L table, a SUMMARY line (win rate,
total/avg P&L, premium spent, return on spend), four heatmaps (win-rate %, win
count, avg P&L, total P&L) on a coarse entry-start × exit-start grid, and a
ranked Top-15 frame-pairs table — then the same again with outliers removed.

Tune the three knobs at the top of `backtest_timeframe.py`:

```python
LOOKBACK_DAYS = 730     # calendar days to test
TARGET_SPEND  = 1.00    # minimum premium per share ($1.00 = ~$100/trade)
OUTLIER_MAX   = 2000    # 2nd pass drops winning trades over $ this
```

## Output files

For each option type, written to `backtest_results/`:

```
backtest_tsla_friday_timeframe_calls_730days_<stamp>.csv
backtest_tsla_friday_timeframe_calls_730days_<stamp>.txt
backtest_tsla_friday_timeframe_calls_730days_<stamp>_outliers_removed.txt
backtest_tsla_friday_timeframe_puts_730days_<stamp>.csv          (and .txt, _outliers_removed.txt)
```

- **CSV** — structured data: per-Friday detail, the optimal-frames summary, and
  the Top-15 frame pairs.
- **TXT** — the full human-readable analysis (tables + heatmaps + top pairs),
  with the outliers-removed pass appended.
- **`_outliers_removed.txt`** — just the outlier-removed, re-optimized analysis.

## Project layout

```
backtest_timeframe.py    entry point — knobs + size/score functions
timeframe_engine.py      core: coarse→fine frame search, heatmaps, top-15, I/O
config.py                TSLA, full-session window (minutes), both option types
models.py                OptionContract, BacktestResult, TradeRecord
utils/                   Black-Scholes (call + put), Friday dates, OCC symbols
data/                    alpaca_fetcher (primary) + yf_fetcher (fallback)
analysis/backtester.py   full-day 1-min capture for both call and put per Friday
backtest_results/        output (CSV + TXT per option type)
```

> **Disclaimer:** For research/education. Not financial advice. Past
> probabilities do not guarantee future results.
