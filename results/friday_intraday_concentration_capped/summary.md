### Results (With Outliers)

Uncapped ("pass 1") — every trade counted, including the fat-tail winners. Aggregated across all 7 tickers by option type.

| Metric | Calls | Puts |
|---|---|---|
| Trades | 648 | 656 |
| Win rate | 35.2% | 38.3% |
| Total P&L | $94,335.02 | $57,825.52 |
| Avg P&L | $145.58 | $88.15 |
| Best trade | $29,896.00 (GOOGL) | $25,997.40 (ORCL) |
| Worst trade | -$482.43 (TSLA) | -$557.11 (GOOGL) |
| Best entry → exit | GOOGL 3:32–3:37 PM → 3:55–4:00 PM ($34,244) | ORCL 2:55–3:00 PM → 3:26–3:31 PM ($25,639) |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

**Combined:** 1,304 trades · 36.7% win rate · **$152,160.54** total P&L · Sharpe 0.081 · max drawdown -$2,907.64.

### Results (Without Outliers)

No `outliers_removed` object is present in `metrics.json`. This strategy's second pass is instead a **concentration cap** (`concentration_capped`): pass 2 re-selects, for each leg, the best time-frame whose single largest winning trade is ≤ 51% of that leg's net P&L — no trade is dropped, but frames whose profits hinge on one lottery ticket are excluded. That is the closest analogue to a without-outliers view, so it is shown here.

| Metric | Calls | Puts |
|---|---|---|
| Trades | 680 | 663 |
| Win rate | 41.3% | 46.8% |
| Total P&L | $28,950.40 | $25,445.01 |
| Avg P&L | $42.57 | $38.38 |
| Best trade | $2,935.09 (GOOGL) | $2,491.20 (NVDA) |
| Worst trade | -$482.43 (TSLA) | -$562.43 (TSLA) |
| Best entry → exit | TSLA 9:40–9:45 AM → 1:45–1:52 PM ($9,860) | TSLA 9:52–9:57 AM → 10:27–10:34 AM ($5,967) |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

**Combined:** 1,343 trades · 44.0% win rate · **$54,395.41** total P&L · Sharpe 0.149 · max drawdown -$2,291.64.

### Oracle's Verdict

This edge is largely a fat-tail mirage. The uncapped $152K total collapses to $54K — a **64% haircut** — once the concentration cap forbids frames that lean on a single jackpot, and the damage is grotesquely local: the uncapped GOOGL_CALL ($34,244) and AMZN_CALL ($25,806) frames each had one trade worth ~100% of the leg's net P&L (GOOGL's single_trade_share 0.87 on a $29,896 print; AMZN's 1.01 on a $25,977 print), and ORCL_PUT ($25,639) rode a single $25,997 winner. Strip those and the "strategy" is a low-win-rate, thin-average grind: even capped, calls win only 41% and puts 47% with avg P&L under $43, and the Sharpe is a feeble 0.081→0.149 — statistically indistinguishable from noise. The good news is the data is REAL Alpaca option bars (not simulated) and the sample is healthy at ~90–104 trades per leg, so this isn't a data artifact; the bad news is that the honest, tradeable number is the capped one, and a 0DTE Friday book earning ~$40/trade before slippage and per-contract commissions on 0DTE options is unlikely to survive real fills. **Verdict: inconclusive-to-negative — the uncapped P&L is not tradeable, and the capped residual is too weak (Sharpe ~0.15) and too commission-sensitive to trust as a live edge.**
