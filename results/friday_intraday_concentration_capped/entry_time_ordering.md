# Friday intraday — entry-time ordering (concentration-capped strategy)

Source: `results/friday_intraday_concentration_capped/metrics.json` · lookback **730 days** · data **REAL Alpaca option bars** · concentration cap **51%**.

Each leg is one **(equity, call/put)** with its optimal intraday **entry window** and **exit window** on Fridays (0DTE). *Top-trade share* = biggest single winning trade ÷ that leg's net total P&L (the figure the cap tests). The **hold window** used for overlap is entry-start → exit-end.

- **WITHOUT cap** = pass 1, unconstrained best frame.
- **WITH cap** = pass 2, best frame whose top-trade share ≤ 51%.

---
## WITHOUT concentration cap (pass 1 — unconstrained)

*Portfolio (pass rollup): 1304 trades · win 36.7% · total $152,161 · Sharpe 0.081 · max DD $-2,908.*

### Chronological — ordered by entry time (market open first)

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Top‑trade share |
|--:|---|---|---|---|--:|--:|--:|--:|
| 1 | 9:40 AM–9:55 AM | 11:50 AM–12:25 PM | GOOGL | PUT | 38% | 104 | $3,209 | 49% |
| 2 | 9:40 AM–9:45 AM | 1:45 PM–1:52 PM | TSLA | CALL | 43% | 101 | $9,860 | 19% |
| 3 | 9:45 AM–9:51 AM | 10:59 AM–11:05 AM | AMZN | PUT | 39% | 104 | $3,129 | 108% |
| 4 | 10:00 AM–10:05 AM | 12:04 PM–12:10 PM | AAPL | PUT | 41% | 103 | $6,990 | 82% |
| 5 | 11:52 AM–11:57 AM | 3:10 PM–3:15 PM | ORCL | CALL | 24% | 67 | $7,568 | 97% |
| 6 | 2:35 PM–2:40 PM | 3:55 PM–4:00 PM | AMZN | CALL | 30% | 100 | $25,806 | 101% |
| 7 | 2:55 PM–3:00 PM | 3:26 PM–3:31 PM | ORCL | PUT | 43% | 56 | $25,639 | 101% |
| 8 | 2:58 PM–3:03 PM | 3:31 PM–3:36 PM | NVDA | CALL | 26% | 101 | $9,478 | 121% |
| 9 | 3:06 PM–3:11 PM | 3:55 PM–4:00 PM | TSLA | PUT | 28% | 98 | $9,580 | 122% |
| 10 | 3:20 PM–3:25 PM | 3:50 PM–3:55 PM | MSFT | PUT | 41% | 91 | $3,553 | 77% |
| 11 | 3:25 PM–3:30 PM | 3:51 PM–3:56 PM | NVDA | PUT | 41% | 100 | $5,725 | 56% |
| 12 | 3:32 PM–3:37 PM | 3:55 PM–4:00 PM | GOOGL | CALL | 43% | 90 | $34,244 | 87% |
| 13 | 3:45 PM–3:50 PM | 3:55 PM–4:00 PM | MSFT | CALL | 37% | 91 | $3,596 | 41% |
| 14 | 3:50 PM–3:55 PM | 3:55 PM–4:00 PM | AAPL | CALL | 41% | 98 | $3,783 | 69% |

### By equity — call & put paired (with time-overlap check)

### GOOGL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 3:32 PM–3:37 PM | 3:55 PM–4:00 PM | 3:32 PM–4:00 PM | 43% | $34,244 | 87% |
| PUT | 9:40 AM–9:55 AM | 11:50 AM–12:25 PM | 9:40 AM–12:25 PM | 38% | $3,209 | 49% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### TSLA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:40 AM–9:45 AM | 1:45 PM–1:52 PM | 9:40 AM–1:52 PM | 43% | $9,860 | 19% |
| PUT | 3:06 PM–3:11 PM | 3:55 PM–4:00 PM | 3:06 PM–4:00 PM | 28% | $9,580 | 122% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### AMZN

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 2:35 PM–2:40 PM | 3:55 PM–4:00 PM | 2:35 PM–4:00 PM | 30% | $25,806 | 101% |
| PUT | 9:45 AM–9:51 AM | 10:59 AM–11:05 AM | 9:45 AM–11:05 AM | 39% | $3,129 | 108% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### AAPL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 3:50 PM–3:55 PM | 3:55 PM–4:00 PM | 3:50 PM–4:00 PM | 41% | $3,783 | 69% |
| PUT | 10:00 AM–10:05 AM | 12:04 PM–12:10 PM | 10:00 AM–12:10 PM | 41% | $6,990 | 82% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### ORCL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 11:52 AM–11:57 AM | 3:10 PM–3:15 PM | 11:52 AM–3:15 PM | 24% | $7,568 | 97% |
| PUT | 2:55 PM–3:00 PM | 3:26 PM–3:31 PM | 2:55 PM–3:31 PM | 43% | $25,639 | 101% |

> **Overlap:** **20 min** — both held together 2:55 PM–3:15 PM.

### NVDA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 2:58 PM–3:03 PM | 3:31 PM–3:36 PM | 2:58 PM–3:36 PM | 26% | $9,478 | 121% |
| PUT | 3:25 PM–3:30 PM | 3:51 PM–3:56 PM | 3:25 PM–3:56 PM | 41% | $5,725 | 56% |

> **Overlap:** **11 min** — both held together 3:25 PM–3:36 PM.

### MSFT

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 3:45 PM–3:50 PM | 3:55 PM–4:00 PM | 3:45 PM–4:00 PM | 37% | $3,596 | 41% |
| PUT | 3:20 PM–3:25 PM | 3:50 PM–3:55 PM | 3:20 PM–3:55 PM | 41% | $3,553 | 77% |

> **Overlap:** **10 min** — both held together 3:45 PM–3:55 PM.


---

## WITH concentration cap (pass 2 — top-trade share ≤ 51%)

*Portfolio (pass rollup): 1343 trades · win 44.0% · total $54,395 · Sharpe 0.149 · max DD $-2,292.*

### Chronological — ordered by entry time (market open first)

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Top‑trade share |
|--:|---|---|---|---|--:|--:|--:|--:|
| 1 | 9:30 AM–9:35 AM | 9:50 AM–9:55 AM | NVDA | CALL | 47% | 104 | $882 | 48% |
| 2 | 9:40 AM–9:55 AM | 11:50 AM–12:25 PM | GOOGL | PUT | 38% | 104 | $3,209 | 49% |
| 3 | 9:40 AM–9:45 AM | 1:45 PM–1:52 PM | TSLA | CALL | 43% | 101 | $9,860 | 19% |
| 4 | 9:41 AM–9:50 AM | 12:55 PM–1:00 PM | AAPL | CALL | 37% | 104 | $3,060 | 33% |
| 5 | 9:52 AM–9:57 AM | 10:27 AM–10:34 AM | TSLA | PUT | 47% | 104 | $5,967 | 17% |
| 6 | 9:58 AM–10:03 AM | 11:08 AM–11:13 AM | ORCL | CALL | 46% | 81 | $3,678 | 16% |
| 7 | 10:12 AM–10:25 AM | 12:00 PM–12:15 PM | AAPL | PUT | 47% | 103 | $2,858 | 48% |
| 8 | 10:23 AM–10:28 AM | 10:31 AM–10:36 AM | AMZN | PUT | 59% | 104 | $865 | 15% |
| 9 | 10:50 AM–10:58 AM | 11:45 AM–12:08 PM | AMZN | CALL | 45% | 104 | $2,008 | 27% |
| 10 | 10:53 AM–10:58 AM | 2:54 PM–2:59 PM | ORCL | PUT | 47% | 55 | $5,059 | 38% |
| 11 | 3:20 PM–3:25 PM | 3:37 PM–3:56 PM | MSFT | PUT | 46% | 93 | $2,447 | 49% |
| 12 | 3:25 PM–3:30 PM | 3:50 PM–3:55 PM | NVDA | PUT | 44% | 100 | $5,040 | 49% |
| 13 | 3:30 PM–3:51 PM | 3:54 PM–3:59 PM | GOOGL | CALL | 35% | 95 | $5,866 | 50% |
| 14 | 3:45 PM–3:50 PM | 3:55 PM–4:00 PM | MSFT | CALL | 37% | 91 | $3,596 | 41% |

### By equity — call & put paired (with time-overlap check)

### NVDA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:30 AM–9:35 AM | 9:50 AM–9:55 AM | 9:30 AM–9:55 AM | 47% | $882 | 48% |
| PUT | 3:25 PM–3:30 PM | 3:50 PM–3:55 PM | 3:25 PM–3:55 PM | 44% | $5,040 | 49% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### GOOGL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 3:30 PM–3:51 PM | 3:54 PM–3:59 PM | 3:30 PM–3:59 PM | 35% | $5,866 | 50% |
| PUT | 9:40 AM–9:55 AM | 11:50 AM–12:25 PM | 9:40 AM–12:25 PM | 38% | $3,209 | 49% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### TSLA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:40 AM–9:45 AM | 1:45 PM–1:52 PM | 9:40 AM–1:52 PM | 43% | $9,860 | 19% |
| PUT | 9:52 AM–9:57 AM | 10:27 AM–10:34 AM | 9:52 AM–10:34 AM | 47% | $5,967 | 17% |

> **Overlap:** **42 min** — both held together 9:52 AM–10:34 AM.

### AAPL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:41 AM–9:50 AM | 12:55 PM–1:00 PM | 9:41 AM–1:00 PM | 37% | $3,060 | 33% |
| PUT | 10:12 AM–10:25 AM | 12:00 PM–12:15 PM | 10:12 AM–12:15 PM | 47% | $2,858 | 48% |

> **Overlap:** **123 min** — both held together 10:12 AM–12:15 PM.

### ORCL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:58 AM–10:03 AM | 11:08 AM–11:13 AM | 9:58 AM–11:13 AM | 46% | $3,678 | 16% |
| PUT | 10:53 AM–10:58 AM | 2:54 PM–2:59 PM | 10:53 AM–2:59 PM | 47% | $5,059 | 38% |

> **Overlap:** **20 min** — both held together 10:53 AM–11:13 AM.

### AMZN

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 10:50 AM–10:58 AM | 11:45 AM–12:08 PM | 10:50 AM–12:08 PM | 45% | $2,008 | 27% |
| PUT | 10:23 AM–10:28 AM | 10:31 AM–10:36 AM | 10:23 AM–10:36 AM | 59% | $865 | 15% |

> **Overlap:** none — the call and put hold windows do **not** intersect.

### MSFT

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 3:45 PM–3:50 PM | 3:55 PM–4:00 PM | 3:45 PM–4:00 PM | 37% | $3,596 | 41% |
| PUT | 3:20 PM–3:25 PM | 3:37 PM–3:56 PM | 3:20 PM–3:56 PM | 46% | $2,447 | 49% |

> **Overlap:** **11 min** — both held together 3:45 PM–3:56 PM.

