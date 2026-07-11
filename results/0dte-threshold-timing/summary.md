The write to `summary.md` wasn't granted. Here is the complete markdown for `results/0dte-threshold-timing/summary.md` — grant the write (or let me retry) and I'll save it:

---

**Verdict:** Real, large-sample study — but this is a threshold-timing *sweep*, not a P&L strategy. On honest out-of-sample `market` fills only **15** symbol/direction/moneyness combos clear zero expectancy, all deep-ITM with razor-thin edge. Directional intraday 0DTE buying is confirmed as a spread-eaten coin-flip.

### Results (With Outliers)

No Calls/Puts P&L split is emitted by this strategy — it produces a timing/threshold sweep rather than a traded book, so the run-level metrics are shown as a single table.

| Metric | Value |
|---|---|
| Data source | REAL Alpaca option bars (last-trade close) + modeled spread |
| Date range | 2025-07-11 → 2026-07-10 (251 sessions) |
| Universe | AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, ORCL, AMD |
| Contract-minutes scanned | 9,141,324 |
| Threshold instances | 3,410,242 |
| Time/threshold buckets | 18,278 |
| Mode C positive `market` combos | 15 (all ITM; thin edge) |
| Validation | mid ≥ market ✅ · regimes ❌ · no overlap ✅ · spot-check ✅ |

### Results (Without Outliers)

No `outliers_removed` block is present in `metrics.json` — this strategy does not run a with/without-outliers pass, so there is no separate without-outliers table.

### Oracle's Verdict

The edge is **real data but barely a real edge**. Across 3.4M threshold instances on genuine Alpaca option bars, the only version that survives honestly — Mode C, out-of-sample, on `market` (spread-paying) fills — leaves just 15 positive combos, every one of them deep-ITM (T% 50–100), with per-day expectancy of ~0.002–0.027 and win rates as low as 3–28%. That profile is the classic 0DTE trap: the high-probability, low-payout trades win often but the occasional −100% forced exit erases the gains, and the `mid − market` gap table shows the spread's bite widening from 1.7 pts ITM to 12.0 pts OTM2+ — so cheap OTM lottery tickets are exactly where the edge dies. The `mid`-fill and hindsight Mode A/B numbers look far rosier but are not tradeable; only take direction from Mode C. Two data-integrity caveats: **regime detection FAILED** because the true-0DTE names show only ~0.35–0.38 0DTE share (the sweep is mixing in Mon→Fri multi-day holds), and **ORCL/AMD list Friday weeklies only**, so their "0DTE" rows are actually multi-day theta/vega bridges and must not be pooled with the real 0DTE names. Bottom line: useful as an entry-timing map (peaks cluster ~35–49 min after a 09:35 open entry, well before the exit windows close), but not evidence of a standalone profitable long-premium strategy — inconclusive-to-negative for anything beyond ITM, and only worth paper-forwarding the ITM Mode C combos.
