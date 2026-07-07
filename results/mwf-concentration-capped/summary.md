I've written the summary. Here is the complete contents of `results/mwf-concentration-capped/summary.md`:

**Verdict:** A positive-looking $17,811 net across 520 trades, but the edge is thin (Sharpe 0.24, 46.5% win rate) and leans on a handful of Friday combos and a per-trade concentration cap that is set loose enough (51%) to let one big win carry a bucket — treat as a research signal, not a live edge.

### Results (With Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 242 | 278 |
| Win rate | 44.2% | 48.6% |
| Total P&L | $11,020 | $6,790 |
| Avg P&L | $45.54 | $24.42 |
| Best trade | $825 | $745 |
| Worst trade | -$305 | -$195 |
| Best entry → exit | AAPL Fri 3:40 PM → 3:55 PM ($4,418) | TSLA Fri 2:15 PM → 3:30 PM ($2,917) |
| Data source | MIXED real + Black-Scholes sim | MIXED real + Black-Scholes sim |

Combined: 520 trades, 46.5% win rate, **$17,810.55** total P&L, $34.25 avg, best trade $825, worst -$305, max drawdown -$1,422, Sharpe 0.238. Ten of twelve day/type buckets were eligible; both Monday call buckets (TSLA, AAPL) had no eligible schedule and were skipped.

### Results (Without Outliers)

No `outliers_removed` block is present in `metrics.json`, so a without-outliers pass is not available for this run. The concentration cap (`largest_single_win / net_total_pnl <= 0.51`) is this strategy's built-in fat-tail guard rather than an outlier-stripped re-run, so the numbers above are the only view.

### Oracle's Verdict

The headline is genuinely positive — every chosen bucket has positive net P&L by construction (that's the eligibility rule), and the mix is broad (2 tickers × 3 days × 2 types, 520 trades). But the quality is uneven. The Friday buckets carry the book: the four Friday combos alone contribute ~$13,000 of the $17,811, and they rest on the longest lookback (730 days) with the lowest win rates (37–46%), meaning they profit from a few large winners rather than consistency — exactly the fat-tail dependence the concentration cap is meant to police, yet a 51% cap still permits a single win to be half a bucket's P&L (TSLA Monday puts sits at 50.4%, right at the line). The short-lookback (140-day) Wednesday/Monday buckets show prettier win rates (55–70%) but on only 18–20 trades each, which is too small to trust. Critically, the aggregate and the TSLA Wednesday buckets are flagged **MIXED real + Black-Scholes sim** — any simulated fills are model output, not tradeable market prints, and inflate confidence. Net: a plausible intraday-drift signal worth watching, but the low Sharpe (0.24), small per-bucket samples, and partial reliance on simulated bars make this inconclusive as a live edge — validate the Friday combos on out-of-sample real data before risking capital.
