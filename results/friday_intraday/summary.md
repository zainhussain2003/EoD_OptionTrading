### Results (With Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 648 | 656 |
| Win rate | 35.2% | 38.3% |
| Total P&L | $94,335.02 | $57,825.52 |
| Avg P&L | $145.58 | $88.15 |
| Best trade | $29,896.00 | $25,997.40 |
| Worst trade | -$482.43 | -$557.11 |
| Best entry → exit | GOOGL 3:32–3:37 PM → 3:55–4:00 PM | ORCL 2:55–3:00 PM → 3:26–3:31 PM |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

*Portfolio (both sides): 1,304 trades · 36.7% win rate · $152,160.54 total P&L · Sharpe 0.08 · max drawdown -$2,907.64.*

### Results (Without Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 671 | 657 |
| Win rate | 41.0% | 43.7% |
| Total P&L | $27,786.65 | $27,130.71 |
| Avg P&L | $41.41 | $41.29 |
| Best trade | $1,963.10 | $1,984.50 |
| Worst trade | -$482.43 | -$562.43 |
| Best entry → exit | TSLA 9:40–9:45 AM → 1:45–1:52 PM | TSLA 9:52–9:57 AM → 10:27–10:34 AM |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

*Portfolio (both sides): 1,328 trades · 42.3% win rate · $54,917.36 total P&L · Sharpe 0.15 · max drawdown -$2,291.64. Outlier cap $2,000/trade; one date removed (2025-06-27).*

### Oracle's Verdict

This edge is overwhelmingly fat-tail-driven and, as configured, is noise dressed as a signal. Removing outlier trades collapses total P&L from **$152,160 to $54,917** — roughly **64% of the headline profit came from a handful of jackpot prints** (GOOGL calls +$29,896, ORCL puts +$25,997, AMZN calls +$25,977, TSLA puts +$11,726), most clustered around a single removed date. The best individual trade falls from ~$26k–30k to under $2k once those are stripped, and the Sharpe of **0.08 (0.15 clean)** is near-zero either way, so on a risk-adjusted basis there is essentially no persistent edge. Win rates sit at a coin-flip-ish 35–44%, meaning the whole thing lives or dies on the rare big winner — a fragile profile for 0DTE longs where the common outcome is decay to zero. The data is **REAL Alpaca option bars** (good, tradeable in principle), but the 5-minute entry/exit windows are almost certainly in-sample-optimized per leg (e.g. GOOGL's "3:32–3:37 → 3:55–4:00" and ORCL's tight afternoon window), so live results would likely regress hard toward the outlier-removed, near-breakeven-after-costs numbers. **Verdict: inconclusive-to-negative — treat as an overfit backtest, not a deployable strategy, until validated out-of-sample with realistic slippage/spread costs.**
