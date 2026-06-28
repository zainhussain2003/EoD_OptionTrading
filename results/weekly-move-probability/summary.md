### Results (With Outliers)

This strategy is a **directional probability study**, not a long/short options P&L backtest, so there is no Calls/Puts split or trade-level P&L. Reporting the single-value summary instead.

| Metric | Value |
|---|---|
| Weeks analyzed (pooled) | 520 |
| P(up ≥ +1.50%) | 36.9% (192/520) |
| P(down ≤ −1.50%) | 35.2% (183/520) |
| P(within ±1.50%) | 27.9% (145/520) |
| Mean weekly return | +0.42% |
| Median weekly return | −0.04% |
| Stdev weekly return | 6.05% |
| Best week | +28.96% |
| Worst week | −19.18% |
| Measurement | Terminal Friday close → next-Friday close |
| Reference window | 3:50–4:00 PM ET (avg of minute closes) |
| Lookback | 730 days (104 wks/ticker) |
| Data source | Real Alpaca Markets API |

**Per-ticker breakdown:**

| Ticker | Weeks | P(up) | P(down) | P(flat) | Mean | Median | Stdev |
|---|---|---|---|---|---|---|---|
| TSLA | 104 | 37.5% | 42.3% | 20.2% | +0.92% | −0.85% | 7.75% |
| AAPL | 104 | 40.4% | 28.8% | 30.8% | +0.36% | +0.53% | 3.85% |
| NVDA | 104 | 42.3% | 35.6% | 22.1% | +0.61% | +0.62% | 6.13% |
| ORCL | 104 | 37.5% | 39.4% | 23.1% | +0.33% | −0.36% | 7.56% |
| MSFT | 104 | 26.9% | 29.8% | 43.3% | −0.11% | −0.22% | 3.59% |

### Results (Without Outliers)

No `outliers_removed` pass is present in `metrics.json` — this strategy reports a single distribution-based result with no outlier-trimmed variant, so there is no second table to show.

### Oracle's Verdict

The result is **real, clean data but a weak/expected edge** — these are unconditional probabilities measured on genuine Alpaca bars across 520 ticker-weeks (104 each, zero dropped), so the sample is decent and tradeable as a *reference*, not a signal. The pooled picture is close to a coin flip with a slightly fat right tail: up 36.9% vs down 35.2% and a flat (±1.50%) bucket of just 27.9%, meaning a ±1.50% weekly move happens ~72% of the time. The gap between the **mean (+0.42%)** and **median (−0.04%)** confirms the average is dragged up by outliers (max +28.96% vs min −19.18%), so the positive drift is fat-tail-driven and should not be read as a per-week expectation. Ticker dispersion is the real story: high-vol names (TSLA, ORCL, NVDA) blow through the band most weeks, while MSFT is range-bound 43% of the time and AAPL leans modestly upward — so the ±1.50% band is far too tight for the volatile names and roughly fair for MSFT/AAPL. Bottom line: a useful base-rate table for sizing weekly straddle/strangle expectations per ticker, but there is **no standalone directional edge** here — up and down are within noise of each other pooled.
