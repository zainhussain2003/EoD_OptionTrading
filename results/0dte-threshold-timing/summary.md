**Verdict: Simulated study — the machinery works, but this is not a tradeable edge.** The run completed cleanly (exit 0) over a 648,000-instance entry-sweep across 9 megacaps, and every internal consistency check passed. But the data is Black-Scholes **SIMULATED**, so none of the numbers below reflect a real market opportunity.

### Results (With Outliers)

This strategy is an entry-timing/threshold sweep, not a directional calls-vs-puts backtest, so there is no Calls/Puts P&L split to report. Falling back to a single metrics table:

| Metric | Value |
|---|---|
| Data source | **SIMULATED (Black-Scholes) — NOT A REAL EDGE** |
| Date range | 2026-01-05 → 2026-03-13 (50 sessions) |
| Universe | AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, ORCL, AMD |
| Contract-minutes swept | 355,500 |
| Entry instances | 648,000 |
| Buckets | 9,360 |
| Mode C positive-market combos | 659 |
| Validation | mid≥market ✓, regimes ✓, no-overlap ✓, spot-check ✓ |

### Results (Without Outliers)

No `outliers_removed` object is present in `metrics.json`, so a without-outliers pass is not available for this run.

### Oracle's Verdict

This is a **research/plumbing run, not a signal** — the headline caveat is baked into the metrics themselves: `data_source` is explicitly "SIMULATED (Black-Scholes) — NOT A REAL EDGE" because `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` were unset and the strategy fell back to synthetic option prices. Any P&L or "positive-market-combo" count derived from Black-Scholes-generated bars is a tautology of the pricing model, not evidence of an exploitable timing threshold. The good news is that the harness is sound: 648,000 instances across 9,360 buckets ran without error, and all four validations passed — mid≥market held across 324,000 compared instances with zero violation groups, and regimes, no-overlap, and spot-check are all clean. That gives confidence the sweep logic and accounting are correct. To turn this into anything tradeable, re-run with real Alpaca option bars so `data_source` reports REAL; until then treat the 659 Mode C positive-market combos as an artifact of the simulator and **inconclusive**.

---

Note: I attempted to write this to `results/0dte-threshold-timing/summary.md` but the write permission wasn't granted. The complete markdown is above — grant the write (or let me retry) and I'll save it to the file.
