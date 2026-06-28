# 🔮 Oracle Verdict — `smoke-test`

**Pipeline plumbing works, but results are from SIMULATED data — not a tradeable conclusion.**

## Metrics

| Metric | Value |
|---|---|
| Trades | 52 |
| Win rate | 44.2% |
| Total P&L | $39.17 |
| Avg / trade | $0.75 |
| Max drawdown | -$181.94 |
| Sharpe | 0.209 |
| Best trade | $14.02 |
| Worst trade | -$131.14 |
| Data source | **SIMULATED** (no Alpaca keys / fetch failed) |

## Interpretation

This run did exactly what a smoke test should: the strategy executed end-to-end, produced 52 trades, and emitted a valid metrics block — the Sentinel → Forge → Oracle → Herald chain is wired correctly. **But the edge here is not real.** The data source is SIMULATED because the Alpaca fetch was rejected (`subscription does not permit querying recent SIP data`), so every number above is a property of the random price generator, not the market.

Even taken at face value, the signal is weak: a Sharpe of 0.21 and a 44.2% win rate mean the small +$39 total P&L is comfortably inside the noise, and the -$182 max drawdown is roughly 4.6× the total profit — a poor reward-to-risk profile. The lone $131 losing trade nearly erases the cumulative gain, underscoring how thin and tail-driven a 52-trade sample is. **Treat this as a successful infrastructure check, not evidence of a profitable strategy.** To draw any real conclusion, the run must hit live Alpaca data.

To get REAL data on the next run, the Alpaca subscription needs to permit recent SIP data, or the strategy should request IEX-feed/older data within the free tier's window. Until then, re-runs will keep producing simulated noise.

## Artifacts

- 📈 Equity curve: `results/smoke-test/equity_curve.png`
- 📄 Trade log: `results/smoke-test/trades.csv`
