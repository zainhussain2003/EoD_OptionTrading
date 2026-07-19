# PLCheck — TSLA calls end-of-day P/L check

A straight profit/loss check (no optimization): **buy the ATM TSLA call at
3:45 PM ET and sell it at 3:55 PM ET**, over the last **730 days**.

TSLA trades 0DTE options on **Fridays**, so those are the days the data-capture
layer produces real option bars — the study evaluates one trade per such day
inside the look-back window (~100 Fridays).

## The rule

- **Entry:** ATM TSLA call at **3:45 PM ET** (`entry_minute = 945`).
- **Exit:** same contract at **3:55 PM ET** (`exit_minute = 955`).
- **Contracts:** `MAX(1, CEILING(budget / (entry_price × 100)))` with a
  **$100** budget — e.g. a $0.50 entry ⇒ ceil(100 / 50) = **2** contracts;
  a $2.00 entry ⇒ ceil(100 / 200) = **1** contract.
- **P/L per trade:** `(exit_price − entry_price) × 100 × contracts`.

The ATM strike is chosen from TSLA's price at the session open, matching the rest
of the repo. If the exact 3:45 / 3:55 minute has no bar, the nearest minute within
`price_tolerance_minutes` (default 3) is used; otherwise the day is skipped.

## Metrics reported (`metrics.json` + summary block)

| Field | Meaning |
|-------|---------|
| `win_rate`, `wins`, `losses` | win percentage and W/L counts |
| `total_pnl`, `avg_pnl` | total and average P/L in dollars |
| `biggest_win`, `biggest_loss` | best and worst single day ($) |
| `profit_concentration` | share of **gross profit** from the single biggest win (≈1.0 ⇒ one trade drove the gains) |
| `loss_concentration` | share of **gross loss** from the single biggest loss |
| `premium_spent`, `return_on_spend` | total premium outlay and P/L ÷ premium |
| `max_drawdown`, `sharpe` | per-trade drawdown / Sharpe |
| `total_contracts` | contracts traded across all days |
| `data_source` | REAL Alpaca bars, SIMULATED, or MIXED |

## Running

```bash
# terminal report only
python backtest_eod.py

# pipeline entry point — also writes metrics.json / trades.csv / equity_curve.png
python strategy.py
```

Set `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` (paper, read-only) for **real** option
bars. Without keys it degrades to a Black-Scholes simulation so the run never goes
silent; the source is always recorded in `metrics.json`.

## Files

| File | Role |
|------|------|
| `config.py` | Knobs: entry/exit minute, budget, look-back, window. |
| `eod_engine.py` | Fixed-window P/L logic, sizing, metrics. |
| `strategy.py` | Pipeline adapter (output contract). |
| `backtest_eod.py` | Standalone terminal report. |
| `analysis/backtester.py`, `data/`, `utils/`, `models.py` | Reused data-capture infra (Alpaca + BS-sim fallback). |

Reuses the data-capture layer from `strategies/tsla-friday-timeframe/`.
