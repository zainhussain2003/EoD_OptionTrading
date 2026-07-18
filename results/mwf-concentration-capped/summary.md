### Results (With Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 280 | 280 |
| Win rate | 43.2% | 46.4% |
| Total P&L | $12,697 | $7,091 |
| Avg P&L | $45.35 | $25.32 |
| Best trade | $1,150 | $745 |
| Worst trade | -$305 | -$195 |
| Best entry → exit | 3:40 PM → 3:55 PM (AAPL Fri, +$4,323) | 2:15 PM → 3:30 PM (TSLA Fri, +$3,020) |
| Data source | REAL Alpaca bars (TSLA Wed = mixed sim) | Real Alpaca option bars |

*Calls and Puts each aggregate the 6 chosen `TICKER|day|type` combos; combined they reconcile to the top-level 560 trades / 44.8% win rate / $19,789 total P&L.*

### Results (Without Outliers)

No `outliers_removed` pass is present in `metrics.json` — this run reports only the with-outliers numbers, so an outlier-stripped comparison is unavailable. Note that concentration is instead governed here by the `max_single_trade_share = 0.51` eligibility cap: every chosen combo keeps its single largest win below 51% of its net P&L (highest observed is TSLA Wednesday calls at 49.2%), so no one trade dominates a bucket.

### Oracle's Verdict

The headline is genuinely positive-and-broad: +$19,789 across 560 trades, positive P&L in **all 12** chosen combos, and a concentration cap that provably prevents any single fat-tail win from carrying a bucket (max share 49%, under the 51% limit). That cap does real work — it screens out the "one lucky day" edges that usually inflate these scans. Confidence is uneven, though: the Friday combos rest on ~101 trades each (730-day lookback) and are the backbone of the P&L (~$12.7k of the $19.8k), while the Monday/Wednesday combos have only 19–20 trades on a 140-day lookback — too thin to distinguish edge from noise, and their high win rates (up to 65%) should be treated as provisional. The overall Sharpe of 0.235 is modest, consistent with an edge that is real but not strong. Two caveats: (1) TSLA Wednesday calls used **mixed real + Black-Scholes simulated** bars, so that combo's $471 is partly modeled and not fully tradeable; and (2) these windows were selected as the best performers in-sample, so expect meaningful decay out-of-sample. Verdict: **plausible, cap-disciplined edge concentrated in the higher-sample Friday buckets** — forward-paper the Friday combos before sizing, and gather more history on the M/W combos before trusting them.
