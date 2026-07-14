I've written the complete `results/tuesday_intraday/summary.md`. Here is its full content:

---

Tuesday same-day Mag-7 intraday (Wednesday 1DTE expiry) closed **+$19,118** across **283 trades** at a **65.4% win rate** — but the edge is diluted by simulated option pricing and thin per-leg samples.

### Results (With Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 140 | 143 |
| Win rate | 69.3% | 61.5% |
| Total P&L | $10,436.88 | $8,681.33 |
| Avg P&L | $74.55 | $60.71 |
| Best trade | $983.40 (META) | $2,074.88 (TSLA) |
| Worst trade | -$371.13 (GOOGL) | -$389.31 (TSLA) |
| Best entry → exit | 12:08–12:13 PM → 2:14–2:19 PM (META) | 9:32–9:58 AM → 12:30–12:35 PM (TSLA) |
| Data source | MIXED real + Black-Scholes sim | MIXED real + Black-Scholes sim |

### Results (Without Outliers)

| Metric | Calls | Puts |
|---|---|---|
| Trades | 140 | 143 |
| Win rate | 69.3% | 61.5% |
| Total P&L | $10,436.88 | $8,545.74 |
| Avg P&L | $74.55 | $59.76 |
| Best trade | $983.40 (META) | $1,949.17 (TSLA) |
| Worst trade | -$371.13 (GOOGL) | -$376.84 (TSLA) |
| Best entry → exit | 12:08–12:13 PM → 2:14–2:19 PM (META) | 9:37–9:55 AM → 12:14–12:19 PM (TSLA) |
| Data source | MIXED real + Black-Scholes sim | MIXED real + Black-Scholes sim |

### Oracle's Verdict

The result is **encouraging but inconclusive**, and it is not yet tradeable as-is. Stripping outliers barely moves the needle — total P&L falls only from $19,118 to $18,983 (-0.7%) and Sharpe actually ticks up (0.302 → 0.311) — so this is **not** a fat-tail mirage; the win rate holds at 65.4% and gains are spread across all 14 legs, which is the healthiest sign here. The real caveat is the **data source**: only the two AAPL legs and AMZN_CALL use REAL Alpaca option bars, while every other leg is "MIXED real + Black-Scholes sim," meaning most of this P&L was priced by a model, not a market — sim fills ignore bid/ask spread and slippage, so the true edge is almost certainly thinner. Sample size is also weak: ~16–21 trades per leg (~150 trading days of Tuesdays) is far too few to trust any single leg's win rate, and the standout legs (META_CALL 87.5%, TSLA_PUT +$3,307) are exactly where small-sample luck hides. The overall Sharpe of ~0.31 is modest for a strategy this active. **Bottom line:** a promising, broad-based pattern worth pursuing, but re-run it on real Wednesday-expiry bars only and with more history before treating any leg's timing window as a live signal.

---

Note: the Write was blocked pending a permission grant. Approve the write to `results/tuesday_intraday/summary.md` and it'll be saved for Herald to pick up.
