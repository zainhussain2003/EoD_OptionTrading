### Results (With Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 98 | 96 |
| Win rate | 37.8% | 39.6% |
| Total P&L | $4,494.00 | $2,144.00 |
| Avg P&L | $45.86 | $22.33 |
| Best trade | $1,112.50 | $1,317.50 |
| Worst trade | -$909.00 | -$569.00 |
| Best entry → exit | AAPL 3:58 PM (2.0x), TSLA 3:59 PM (2.5x) → Fri limit-or-3:55 PM | AAPL 3:59 PM (1.5x), TSLA 3:57 PM (2.5x) → Fri limit-or-3:55 PM |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

**Portfolio (all legs):** 194 trades · 38.7% win rate · **$6,638.00** total P&L · $34.22 avg/trade · max drawdown -$3,294.00 · Sharpe 0.079.

### Results (Without Outliers)

No `outliers_removed` block is present in `metrics.json` for this run, so a without-outliers table cannot be produced.

### Oracle's Verdict

The headline $6,638 profit on real Alpaca option bars is almost entirely a TSLA long-premium story: **TSLA_CALL (+$3,865) and TSLA_PUT (+$2,914) supply $6,779 of the total, while AAPL nets a small loss** (+$629 calls, -$770 puts). That concentration is a red flag — the edge rests on two legs of one high-volatility name, and single trades of $1,112 (TSLA call) and $1,317 (TSLA put) show the result is fat-tail-driven; strip those best trades and the cushion thins fast, which a Sharpe of just 0.079 and a -$3,294 drawdown already confirm. Sample size is thin (~48–50 trades and only ~51 weekly pairs per leg, with fill rates of just 23–40%, so many weeks never actually trade), so best-entry-minute and best-target choices are likely overfit to noise rather than a stable signal. Buying weekly premium into Friday expiry is structurally theta-negative, and the log's per-entry P&L grid shows most target/time cells hovering near or below breakeven — consistent with TSLA's realized moves, not a repeatable options mispricing. **Verdict: inconclusive and not yet tradeable** — the data is real, but the profit is a small, outlier- and TSLA-dependent sample; validate on a longer lookback and out-of-sample weeks, and treat AAPL's negative puts as evidence the "buy both directions" template has no reliable directional edge.
