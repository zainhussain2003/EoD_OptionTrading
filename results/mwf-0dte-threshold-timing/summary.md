**Verdict:** Ran clean on a large REAL-data sample and passed every internal validation check — but this run is a **data/threshold sweep, not a P&L backtest**. There are no trades, win rate, or dollar returns to judge an edge from yet.

### Results (With Outliers)

This strategy produced no calls/puts trade split and no P&L metrics — it emits a contract-minute sweep and validation record instead. Falling back to a single `Metric | Value` table.

| Metric | Value |
|---|---|
| Data source | REAL Alpaca option bars (last-trade close) + modeled spread |
| Date range | 2024-07-12 → 2026-07-10 |
| 0DTE sessions | 141 |
| Universe | AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, ORCL, AMD (9) |
| Contract-minutes | 4,233,682 |
| Instances | 1,590,782 |
| Buckets | 4,784 |
| Mode C +ve market combos | 121 |
| Validation: mid ≥ market | ✅ (0 violation groups / 795,391 compared) |
| Validation: regimes | ✅ |
| Validation: no overlap | ✅ |
| Validation: spot check | ✅ |

### Results (Without Outliers)

No `outliers_removed` object is present in `metrics.json`, so there is no without-outliers pass to report for this strategy.

### Oracle's Verdict

There is no edge to confirm or reject here — this run reports **data coverage and internal consistency, not trade profitability**. On the plus side, everything that *can* be judged looks solid: the data is REAL Alpaca 0DTE option bars (not simulated), the sample is enormous (1.59M instances / 4.23M contract-minutes across 141 sessions and 9 liquid names), and all four validation gates passed — including the mid ≥ market check over 795k compared instances with zero violations, which means the modeled spread and pricing logic are behaving. The 121 "Mode C positive-market combos" is the closest thing to a signal, but without P&L, entry/exit timing, or win rates attached to those combos, it's a candidate count, not a result. ORCL (100 sessions) and AMD (98 sessions) have thinner coverage than the ~140-session core, so any per-symbol conclusions on those two are weaker. **Bottom line: infrastructure and data are validated and trustworthy, but the strategy still needs a P&L-producing pass — emitting trades, win rate, and returns per Mode C combo — before any of this is tradeable.**
