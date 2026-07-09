The summary was blocked pending write permission, so I'll output the complete contents of `results/thursday-intraday/summary.md` here:

---

# 🔮 Oracle Summary — thursday-intraday

**Verdict:** A real-data 730-day backtest of same-session Thursday AAPL & TSLA calls and puts. Across 390 trades the book made **+$21,261** at a **52.0%** win rate — but the edge is almost entirely one leg (TSLA puts) and heavily tail-driven. Treat as **inconclusive / not yet tradeable per-leg.**

### Results (With Outliers)

| Metric | Calls (AAPL + TSLA) | Puts (AAPL + TSLA) |
|---|---|---|
| Trades | 195 | 195 |
| Win rate | 51.8% (101/195) | 52.3% (102/195) |
| Total P&L | $3,312.01 | $17,949.11 |
| Avg P&L | $16.98 | $92.05 |
| Best trade | $817.20 (TSLA) | $3,933.69 (TSLA) |
| Worst trade | -$388.10 (TSLA) | -$858.90 (TSLA) |
| Best entry → exit | AAPL 10:08–10:13 → 10:36–10:41 AM · TSLA 12:31–12:36 → 1:00–1:15 PM | AAPL 9:30–9:35 → 9:42–9:49 AM · TSLA 9:31–9:36 AM → 3:15–3:25 PM |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

*Per-leg totals: AAPL_CALL $1,736 (54% win) · TSLA_CALL $1,576 (49%) · AAPL_PUT $2,058 (54%) · TSLA_PUT $15,892 (51%).*

### Results (Without Outliers)

| Metric | Calls (AAPL + TSLA) | Puts (AAPL + TSLA) |
|---|---|---|
| Trades | 195 | 195 |
| Win rate | 51.8% (101/195) | 52.3% (102/195) |
| Total P&L | $3,312.01 | $14,223.12 |
| Avg P&L | $16.98 | $72.94 |
| Best trade | $817.20 (TSLA) | $1,916.70 (TSLA) |
| Worst trade | -$388.10 (TSLA) | -$669.84 (TSLA) |
| Best entry → exit | AAPL 10:08–10:13 → 10:36–10:41 AM · TSLA 12:31–12:36 → 1:00–1:15 PM | AAPL 9:30–9:35 → 9:42–9:49 AM · TSLA 9:46–9:51 AM → 2:15–2:39 PM |
| Data source | REAL Alpaca option bars | REAL Alpaca option bars |

*Book total drops from $21,261 → $17,535 and Sharpe ticks up 0.151 → 0.165. Only the TSLA_PUT leg changes (re-optimized frame $15,892 → $12,166); the call legs and both AAPL legs are identical because none of their trades exceeded the $2,000 outlier cap.*

### Oracle's Verdict

The data is **real Alpaca option bars** over 730 days, which is the right starting point, but the headline P&L is not evenly distributed. **TSLA puts alone account for ~75% of total profit** ($15,892 of $21,261 with outliers), and that leg's edge is fat-tail-driven: removing trades above $2,000 cuts its P&L by $3,726 (–23%) while the entire rest of the book is unchanged. Stripping outliers barely moves the book Sharpe (0.15 → 0.17), and even the "with outliers" Sharpe of 0.15 is very low for a strategy leaning this hard on a single leg's best days. The win rates cluster tightly around 50–54% across all four legs — closer to a coin flip than a durable directional edge — so the money is coming from asymmetric payoff on a handful of TSLA sessions, not from consistently being right. Sample size is modest (~97–98 trades per leg), and the "optimal" entry/exit frames are the product of an in-sample grid search, which will overstate live performance. **Bottom line:** the framework and data are sound, but this looks like an over-fit, tail-dependent result — the AAPL and TSLA-call legs are near break-even after costs, and the TSLA-put edge needs out-of-sample confirmation before it's tradeable.

---

Note: the `Write` call was denied (no permission granted for `results/thursday-intraday/summary.md`), so the file was **not** written to disk. If you want me to save it, approve the write and I'll re-run it.
