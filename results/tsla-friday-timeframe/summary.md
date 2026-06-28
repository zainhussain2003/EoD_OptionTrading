I've written the complete `results/tsla-friday-timeframe/summary.md`. Here are its contents:

---

# TSLA Friday Time-Frame — Summary

**Verdict: Profitable on paper, but the edge is fat-tail-driven and likely overfit — treat as inconclusive.**

## Metrics

| Metric | Overall | Calls | Puts |
|---|---|---|---|
| Trades | 202 | 102 | 100 |
| Win rate | 34.6% | 42.2% | 27.0% |
| Total P&L | $18,927.11 | $9,686.37 | $9,240.74 |
| Avg / trade | $93.70 | $94.96 | $92.41 |
| Best trade | $11,726.40 | $1,906.49 | $11,726.40 |
| Worst trade | -$482.43 | -$482.43 | -$476.00 |
| Max drawdown | -$2,235.90 | — | — |
| Sharpe | 0.103 | — | — |
| Return on spend | — | 24.4% | 22.3% |
| Entry → Exit | — | 9:40–9:45 → 1:45–1:52 | 3:06–3:11 → 3:55–4:00 |
| Data source | REAL Alpaca option bars | | |

## Interpretation

The headline total of **+$18.9k over 202 trades on real option bars** looks strong, but the shape of the returns is the story. The **win rate is only 34.6%** and the **Sharpe is 0.103** — essentially flat risk-adjusted. This is a strategy that loses on most Fridays and is bailed out by a handful of large winners.

That dependence is extreme on the puts side: a **single $11,726 day accounts for ~127% of the entire put P&L** ($9,241 total). Strip that one Friday out and the put book is *negative* over two years — its 27% win rate is what you'd expect from buying premium with no real edge. The calls book is more believable (42% win rate, top winner only ~$1,900, no single day dominating), but its Sharpe-equivalent is still thin.

Two further cautions. **Selection bias / overfitting:** the run scanned the full grid of entry/exit frames and reported the *best* pairs (see the PUTS top-15 table in the log, where dozens of 5-minute windows cluster within a few hundred dollars of each other). The chosen frames (9:40–9:45 calls, 3:06–3:11 puts) are in-sample optima, not out-of-sample validated — expect material decay live. **Sample size:** ~100 Fridays per side is modest for a result this tail-dependent; the confidence interval on win rate and average P&L is wide.

Bottom line: data is REAL (good), but the result is **inconclusive and not yet tradeable**. Validate on a held-out period (e.g. split the 730 days in half, or forward-test the next quarter) and re-check whether the edge survives removing the top 1–2 days.

## Artifacts

- Equity curve: `results/tsla-friday-timeframe/equity_curve.png`
- Per-trade detail: `results/tsla-friday-timeframe/trades.csv`
- Full frame-pair scans (calls/puts CSV + TXT): `results/tsla-friday-timeframe/backtest_tsla_friday_timeframe_*`

---

Note: the write was blocked pending permission. Grant write access to that path (or approve the pending call) and I'll save it — the content above is final.
