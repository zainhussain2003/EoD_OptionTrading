I've written the summary to `results/PLCheck/summary.md` (pending your permission to save it). It leads with the verdict and covers the required sections:

- **Results (With Outliers)** — single Metric | Value table since PLCheck is a calls-only strategy with no puts leg.
- **Results (Without Outliers)** — noted as unavailable, since `metrics.json` has no `outliers_removed` object.
- **Oracle's Verdict** — the edge is real (+$4,187, +9.2% on premium) on REAL Alpaca data, but thin and fat-tail-dependent: a 43.9% win rate, Sharpe 0.22, and 20.5% profit concentration in a single winner. With n=98 and no outlier-removed pass to gauge robustness, I've flagged it **inconclusive**.

Approve the write and it'll land in `results/PLCheck/summary.md` for Herald to pick up.
