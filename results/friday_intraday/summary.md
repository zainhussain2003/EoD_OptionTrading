### Results (With Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 648 | 656 |
| Win rate | 35.2% | 38.3% |
| Total P&L | $94,335 | $57,826 |
| Avg P&L | $145.58 | $88.15 |
| Best trade | $29,896 | $25,997 |
| Worst trade | -$482.43 | -$557.11 |
| Best entry → exit | GOOGL 3:32–3:37 PM → 3:55–4:00 PM ($34,244) | ORCL 2:55–3:00 PM → 3:26–3:31 PM ($25,639) |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

*Aggregated across all 7 tickers (14 legs). Combined: 1,304 trades, $152,161 total P&L, Sharpe 0.081, max drawdown -$2,908.*

### Results (Without Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 671 | 657 |
| Win rate | 41.0% | 43.7% |
| Total P&L | $27,787 | $27,131 |
| Avg P&L | $41.41 | $41.29 |
| Best trade | $1,963 | $1,985 |
| Worst trade | -$482.43 | -$562.43 |
| Best entry → exit | TSLA 9:40–9:45 AM → 1:45–1:52 PM ($9,860) | TSLA 9:52–9:57 AM → 10:27–10:34 AM ($5,967) |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

*Combined: 1,328 trades, $54,917 total P&L, Sharpe 0.15, max drawdown -$2,292. Outlier cap $2,000/trade removed a single date: 2025-06-27.*

### Oracle's Verdict

The headline number is a mirage. Removing outliers erases **64% of the P&L** ($152k → $55k), and nearly all of that erased profit traces to one session — **2025-06-27** — which produced GOOGL_CALL's $29,896, ORCL_PUT's $25,997, AMZN_CALL's $25,977, and NVDA/TSLA five-figure spikes. Strip that one day and no single leg clears ~$10k; the edge is overwhelmingly fat-tail-driven, not a repeatable intraday pattern. The data is REAL Alpaca option bars (a genuine positive), and the without-outliers version is still net-positive at ~$41/trade with a 42% win rate across 1,328 trades — but a Sharpe of 0.15 is essentially noise, and the per-leg entry/exit windows are suspiciously precise and **shift wildly between the with- and without-outlier passes** (e.g. AAPL_CALL flips from 3:50 PM to 9:34 AM), the signature of in-sample curve-fitting rather than a stable structural edge. **Verdict: inconclusive-to-weak.** Treat the $152k as one lucky day, not an edge; the honest, outlier-scrubbed result is a thin, low-Sharpe positive drift that would need walk-forward / out-of-sample validation on locked entry/exit frames before anyone should trust it.
