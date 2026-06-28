### Results (With Outliers)

This strategy is a **price-level-touch probability study**, not a P&L backtest — there are no trades, win rate, or dollar P&L to report. It measures, for each ticker, how often Friday's intraday price swings **up** or **down** past a per-ticker dollar threshold relative to a Thursday-close reference (3:50–3:55 PM ET). The table below uses the recommended reference time (**3:52 PM** for all five tickers) from the with-outliers data; `target_spend` was $1 and `outlier_max` was $2,000.

| Metric | TSLA | AAPL | NVDA | MSFT | ORCL |
|---|---|---|---|---|---|
| Threshold ($) | 8.0 | 6.0 | 5.0 | 10.0 | 7.0 |
| Fridays analyzed | 101 | 101 | 101 | 101 | 100 |
| Up-touch rate | 51.5% | 13.9% | 13.9% | 8.9% | 13.0% |
| Down-touch rate | 36.6% | 9.9% | 24.8% | 12.9% | 17.0% |
| Both-touch rate | 7.9% | 0.0% | 0.0% | 0.0% | 0.0% |
| Neither rate | 19.8% | 76.2% | 61.4% | 78.2% | 70.0% |
| Avg up swing ($) | 8.96 | 2.90 | 2.27 | 4.08 | 2.74 |
| Avg down swing ($) | 6.25 | 2.30 | 2.68 | 4.02 | 3.46 |
| Max up / down swing ($) | 31.85 / 31.39 | 13.74 / 14.96 | 15.74 / 14.77 | 25.15 / 14.76 | 22.50 / 27.98 |
| Recommended reference | 3:52 PM | 3:52 PM | 3:52 PM | 3:52 PM | 3:52 PM |
| Reference deviation (steadiness) | 0.235 | 0.105 | 0.083 | 0.170 | 0.084 |
| Data source | Real Alpaca API | Real Alpaca API | Real Alpaca API | Real Alpaca API | Real Alpaca API |

Across all five tickers, **3:52 PM** was the steadiest reference minute (lowest deviation) of the 3:50–3:55 window, and was preferred over the 3:50–55 average everywhere.

### Results (Without Outliers)

No separate without-outliers pass is present — `metrics.json` contains no `outliers_removed` object, so there is nothing to report here. The run was bounded by a single `outlier_max` of $2,000 (no extreme swings approached that cap; the largest observed move was ~$32 on TSLA), so the with-outliers numbers above are effectively the full, unfiltered result.

### Oracle's Verdict

The signal is **real data, modest edge, and asymmetric by ticker** — this is genuine Alpaca history over ~101 Fridays per name (2 years), which is a respectable sample, not simulation, so it is informative. The clearest result is **TSLA**: at its $8 threshold it touches *up* on 51.5% of Fridays vs *down* 36.6%, with the average up swing ($8.96) exceeding the average down ($6.25) — a persistent upward-drift tilt worth a directional look. The other four are much quieter: AAPL/MSFT spend ~76–78% of Fridays touching *neither* threshold, meaning their dollar thresholds are set well outside typical Friday range and rarely trigger. **NVDA is the lone down-skewed name** (24.8% down vs 13.9% up), and ORCL leans mildly down with the fattest tail (a $27.98 max down swing). The "both-touch" rate is ~0% everywhere except TSLA (7.9%), so for most names a touch is a clean one-directional event. Because thresholds are arbitrary per-ticker dollar levels rather than volatility-normalized, cross-ticker rates aren't directly comparable, and the low trigger frequency on AAPL/MSFT/ORCL means their rates rest on only ~10–17 events each — **directionally suggestive but statistically thin**. Bottom line: TSLA's up-bias is the most tradeable observation; treat the rest as range/threshold-calibration findings rather than edges, and consider re-running with volatility-scaled thresholds before committing capital.
