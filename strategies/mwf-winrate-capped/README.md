# mwf-winrate-capped

Mon/Wed/Fri 0DTE **optimal entry/exit** study for **TSLA & AAPL**, **calls and
puts** — with a **win-rate cap** instead of an outlier system.

## The idea

For each weekday the engine searches every 5-minute (entry, exit) schedule inside
that day's trading window and picks the best one — but *instead of the old
`OUTLIER_MAX` system* (which dropped winning trades over a dollar threshold), the
**selected schedule is constrained by win rate**. Only (entry, exit) pairs whose
win rate lands inside a target band are eligible, so the chosen "best day" is a
realistic **45–50% (±1%)** rather than an overfit, sky-high win rate.

```
eligible ⇔ (MAX_WIN_RATE_LOW − WIN_RATE_TOL) ≤ win_rate ≤ (MAX_WIN_RATE_HIGH + WIN_RATE_TOL)
```

With the defaults the eligible band is **[0.44, 0.51]**. Among eligible schedules
the winner is ranked by `win_rate × avg_payoff`. Position sizing is unchanged from
the sized backtests: `contracts = ceil(TARGET_SPEND / option_price)`, min 1.

## Per-weekday schedule (`DAY_SCHEDULE` in `backtest_byday.py`)

| Day | Lookback | Trading window |
|-----|----------|----------------|
| Monday | 140 days | 3:00–4:00 PM ET |
| Wednesday | 140 days | 3:00–4:00 PM ET |
| Friday | 730 days | 2:00–4:00 PM ET |

Data is captured once over the widest window (2–4 PM) and the longest lookback
(730 days); each weekday is then trimmed to its own lookback + window. Closed
Fridays fall back to the preceding Thursday's **real** option data (never
simulated); Mon/Wed have no fallback.

## The knobs (top of `backtest_byday.py`)

- `DAY_SCHEDULE` — per-weekday `(name, weekday, lookback_days, window_start_hour, window_end_hour)`
- `TARGET_SPEND` — minimum premium per share (`$1.00 ≈ $100/trade`)
- `MAX_WIN_RATE_LOW` / `MAX_WIN_RATE_HIGH` — the target win-rate band edges
- `WIN_RATE_TOL` — ± tolerance around the band

## Files

| File | Role |
|------|------|
| `strategy.py` | Pipeline entry point — emits `metrics.json`, `trades.csv`, `equity_curve.png`, and the summary block. |
| `backtest_byday.py` | Knobs + `run_all()`; run standalone for a terminal report. |
| `byday_engine.py` | Pure scoring core (stats, optimizer, per-day P&L, summary). |
| `analysis/backtester.py` | Captures MWF 0DTE option minutes for both calls and puts, keyed by `(ticker, opt_type)`. |
| `config.py`, `models.py`, `utils/`, `data/` | Shared scaffolding (Alpaca/yfinance fetch, Black-Scholes, date/OCC helpers). |

## Running

```bash
python backtest_byday.py   # terminal summary
python strategy.py         # also writes the pipeline contract artifacts to $STRATEGY_RESULTS_DIR (or ./output)
```

Reads `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` from env; without them it falls back
to Black-Scholes simulation. Alpaca paper + market-data, read-only (no orders).
