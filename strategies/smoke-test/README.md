# EoD Strategy Template

Reference structure for an end-of-day (EoD) option-trading strategy in this repo.
The example implements a **weekly OTM cash-secured put-selling** backtest on SPY.

The **Architect** agent copies this directory into `strategies/<name>/` and edits
the marked sections to implement a new idea. The rest of the pipeline
(Sentinel → Forge → Oracle → Herald) relies on the output contract below.

## Files

| File | Purpose |
|------|---------|
| `strategy.py` | Entry point. Sections 0–5 + `main()`. **Run with `python strategy.py`.** |
| `config.py` | `Config` dataclass — strategy parameters. Edit here for a new idea. |
| `requirements.txt` | Python deps (alpaca-py, pandas, numpy, scipy, matplotlib, dotenv). |
| `.env.example` | Copy to `.env`, add `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`. |

## The output contract (do not break)

`strategy.py` MUST:

1. Read Alpaca keys from env `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.
2. Write artifacts into `STRATEGY_RESULTS_DIR` (set by the pipeline; defaults to
   `./output` when run by hand):
   - `metrics.json` — **required**, machine-readable metrics.
   - `trades.csv` — per-trade ledger.
   - `equity_curve.png` — cumulative P&L chart.
3. Print a fenced JSON block to stdout:
   ```
   ===STRATEGY_SUMMARY_JSON===
   {"status":"ok","n_trades":..,"win_rate":..,"total_pnl":..,"max_drawdown":..,"sharpe":..}
   ===END_SUMMARY===
   ```
4. Exit `0` on success; on crash, write `metrics.json` with `{"status":"error",...}`
   and exit non-zero (the template's `main()` guard already does this).

## Sections in `strategy.py`

- **0 — Output location**: resolves `STRATEGY_RESULTS_DIR`.
- **1 — Pricing helpers**: Black–Scholes put price/delta (also the data fallback).
- **2 — Data loading**: Alpaca underlying bars, with reproducible simulated fallback.
- **3 — Strategy logic + backtest**: ← *the main thing to edit for a new idea.*
- **4 — Metrics**: win rate, P&L, max drawdown, Sharpe. Keys are the Oracle contract.
- **5 — Output**: artifacts + printed summary block.

## Run locally

```powershell
pip install -r requirements.txt
copy .env.example .env   # then add your Alpaca paper keys
python strategy.py
```

Without keys it still runs (simulated underlying), so you can smoke-test the
structure before wiring data.
