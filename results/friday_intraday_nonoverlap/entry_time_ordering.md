# Friday intraday — NON-OVERLAPPING call+put, entry-time ordering

Source: `results/friday_intraday_nonoverlap/metrics.json` · lookback **730 days** · data **REAL Alpaca option bars** · concentration cap **51%**.

These are the **de-conflicted** windows: per equity a call window and a put window whose hold times never overlap (one leg fully exits before the other enters). Each leg's P&L is measured as if traded alone; *combined* is their sum. *Top-trade share* = biggest single winning trade ÷ that leg's net total P&L.

- **WITHOUT cap** = pass 1 (unconstrained frames).
- **WITH cap** = pass 2 (each frame's biggest single win ≤ 51% of its total P&L).

---
## WITHOUT concentration cap (pass 1)

*Non-overlapping combined P&L (sum of both legs, all equities): **$144,126**.*
*Per-leg pass rollup (independent optimum, for reference): 1304 trades · win 36.7% · per-leg total $152,161 · Sharpe 0.081 · max DD $-2,908.*

### Chronological — every leg ordered by entry time (market open first)

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Top‑trade share |
|--:|---|---|---|---|--:|--:|--:|--:|
| 1 | 9:40–9:55 AM | 11:50 AM–12:20 PM | GOOGL | PUT | 37% | 104 | $3,212 | 49% |
| 2 | 9:40–9:45 AM | 1:45–1:50 PM | TSLA | CALL | 43% | 101 | $9,758 | 20% |
| 3 | 9:45–9:50 AM | 11:00–11:05 AM | AMZN | PUT | 39% | 104 | $3,079 | 109% |
| 4 | 10:00–10:05 AM | 11:10–11:15 AM | ORCL | CALL | 44% | 79 | $3,174 | 19% |
| 5 | 10:00–10:05 AM | 12:00–12:10 PM | AAPL | PUT | 40% | 103 | $6,870 | 83% |
| 6 | 2:35–2:40 PM | 3:55–4:00 PM | AMZN | CALL | 30% | 100 | $25,806 | 101% |
| 7 | 2:55–3:00 PM | 3:25–3:30 PM | ORCL | PUT | 45% | 53 | $22,820 | 101% |
| 8 | 3:00–3:05 PM | 3:30–3:35 PM | NVDA | CALL | 27% | 101 | $9,392 | 122% |
| 9 | 3:05–3:10 PM | 3:55–4:00 PM | TSLA | PUT | 25% | 97 | $9,736 | 126% |
| 10 | 3:20–3:25 PM | 3:40–3:45 PM | MSFT | PUT | 48% | 90 | $2,342 | 68% |
| 11 | 3:30–3:35 PM | 3:55–4:00 PM | GOOGL | CALL | 41% | 93 | $34,271 | 87% |
| 12 | 3:45–3:50 PM | 3:55–4:00 PM | MSFT | CALL | 37% | 91 | $3,596 | 41% |
| 13 | 3:45–3:50 PM | 3:55–4:00 PM | NVDA | PUT | 29% | 99 | $6,287 | 106% |
| 14 | 3:50–3:55 PM | 3:55–4:00 PM | AAPL | CALL | 41% | 98 | $3,783 | 69% |

### By equity — call & put paired (de-conflicted; overlap = 0 by design)

### TSLA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:40–9:45 AM | 1:45–1:50 PM | 9:40 AM–1:50 PM | 43% | $9,758 | 20% |
| PUT | 3:05–3:10 PM | 3:55–4:00 PM | 3:05 PM–4:00 PM | 25% | $9,736 | 126% |

> **call-then-put**, handoff **1:50 PM** · overlap **0 min** · gap between legs: **75 min flat** (1:50 PM–3:05 PM) · **combined $19,494**.

### GOOGL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 9:40–9:55 AM | 11:50 AM–12:20 PM | 9:40 AM–12:20 PM | 37% | $3,212 | 49% |
| CALL | 3:30–3:35 PM | 3:55–4:00 PM | 3:30 PM–4:00 PM | 41% | $34,271 | 87% |

> **put-then-call**, handoff **12:20 PM** · overlap **0 min** · gap between legs: **190 min flat** (12:20 PM–3:30 PM) · **combined $37,483**.

### AMZN

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 9:45–9:50 AM | 11:00–11:05 AM | 9:45 AM–11:05 AM | 39% | $3,079 | 109% |
| CALL | 2:35–2:40 PM | 3:55–4:00 PM | 2:35 PM–4:00 PM | 30% | $25,806 | 101% |

> **put-then-call**, handoff **11:05 AM** · overlap **0 min** · gap between legs: **210 min flat** (11:05 AM–2:35 PM) · **combined $28,885**.

### AAPL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 10:00–10:05 AM | 12:00–12:10 PM | 10:00 AM–12:10 PM | 40% | $6,870 | 83% |
| CALL | 3:50–3:55 PM | 3:55–4:00 PM | 3:50 PM–4:00 PM | 41% | $3,783 | 69% |

> **put-then-call**, handoff **12:10 PM** · overlap **0 min** · gap between legs: **220 min flat** (12:10 PM–3:50 PM) · **combined $10,653**.

### ORCL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 10:00–10:05 AM | 11:10–11:15 AM | 10:00 AM–11:15 AM | 44% | $3,174 | 19% |
| PUT | 2:55–3:00 PM | 3:25–3:30 PM | 2:55 PM–3:30 PM | 45% | $22,820 | 101% |

> **call-then-put**, handoff **11:15 AM** · overlap **0 min** · gap between legs: **220 min flat** (11:15 AM–2:55 PM) · **combined $25,994**.

### NVDA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 3:00–3:05 PM | 3:30–3:35 PM | 3:00 PM–3:35 PM | 27% | $9,392 | 122% |
| PUT | 3:45–3:50 PM | 3:55–4:00 PM | 3:45 PM–4:00 PM | 29% | $6,287 | 106% |

> **call-then-put**, handoff **3:35 PM** · overlap **0 min** · gap between legs: **10 min flat** (3:35 PM–3:45 PM) · **combined $15,679**.

### MSFT

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 3:20–3:25 PM | 3:40–3:45 PM | 3:20 PM–3:45 PM | 48% | $2,342 | 68% |
| CALL | 3:45–3:50 PM | 3:55–4:00 PM | 3:45 PM–4:00 PM | 37% | $3,596 | 41% |

> **put-then-call**, handoff **3:45 PM** · overlap **0 min** · gap between legs: back-to-back (handoff, no gap) · **combined $5,938**.


---

## WITH concentration cap (pass 2 — single win ≤ 51%)

*Non-overlapping combined P&L (sum of both legs, all equities): **$43,613**.*
*Per-leg pass rollup (independent optimum, for reference): 1343 trades · win 44.0% · per-leg total $54,395 · Sharpe 0.149 · max DD $-2,292.*

### Chronological — every leg ordered by entry time (market open first)

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Top‑trade share |
|--:|---|---|---|---|--:|--:|--:|--:|
| 1 | 9:30–9:35 AM | 9:50–9:55 AM | NVDA | CALL | 47% | 104 | $882 | 48% |
| 2 | 9:40–9:55 AM | 11:50 AM–12:20 PM | GOOGL | PUT | 37% | 104 | $3,212 | 49% |
| 3 | 9:45–9:55 AM | 10:25–10:30 AM | TSLA | PUT | 48% | 104 | $4,859 | 21% |
| 4 | 9:50–9:55 AM | 11:05–11:25 AM | MSFT | PUT | 44% | 104 | $2,088 | 34% |
| 5 | 10:10–10:25 AM | 12:05–12:20 PM | AAPL | PUT | 43% | 103 | $3,053 | 51% |
| 6 | 10:20–10:25 AM | 10:30–10:35 AM | AMZN | PUT | 54% | 104 | $842 | 22% |
| 7 | 10:25–10:30 AM | 10:40–10:50 AM | ORCL | CALL | 54% | 91 | $2,308 | 17% |
| 8 | 10:30–10:35 AM | 1:50–2:00 PM | TSLA | CALL | 48% | 101 | $6,254 | 25% |
| 9 | 10:50–11:00 AM | 11:50 AM–12:10 PM | AMZN | CALL | 44% | 104 | $1,921 | 29% |
| 10 | 10:55–11:00 AM | 2:55–3:00 PM | ORCL | PUT | 46% | 56 | $4,174 | 33% |
| 11 | 3:25–3:30 PM | 3:50–3:55 PM | NVDA | PUT | 44% | 100 | $5,040 | 49% |
| 12 | 3:25–3:55 PM | 3:55–4:00 PM | GOOGL | CALL | 39% | 95 | $3,096 | 45% |
| 13 | 3:40–3:45 PM | 3:55–4:00 PM | AAPL | CALL | 38% | 100 | $2,287 | 32% |
| 14 | 3:45–3:50 PM | 3:55–4:00 PM | MSFT | CALL | 37% | 91 | $3,596 | 41% |

### By equity — call & put paired (de-conflicted; overlap = 0 by design)

### NVDA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 9:30–9:35 AM | 9:50–9:55 AM | 9:30 AM–9:55 AM | 47% | $882 | 48% |
| PUT | 3:25–3:30 PM | 3:50–3:55 PM | 3:25 PM–3:55 PM | 44% | $5,040 | 49% |

> **call-then-put**, handoff **9:55 AM** · overlap **0 min** · gap between legs: **330 min flat** (9:55 AM–3:25 PM) · **combined $5,922**.

### GOOGL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 9:40–9:55 AM | 11:50 AM–12:20 PM | 9:40 AM–12:20 PM | 37% | $3,212 | 49% |
| CALL | 3:25–3:55 PM | 3:55–4:00 PM | 3:25 PM–4:00 PM | 39% | $3,096 | 45% |

> **put-then-call**, handoff **12:20 PM** · overlap **0 min** · gap between legs: **185 min flat** (12:20 PM–3:25 PM) · **combined $6,308**.

### TSLA

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 9:45–9:55 AM | 10:25–10:30 AM | 9:45 AM–10:30 AM | 48% | $4,859 | 21% |
| CALL | 10:30–10:35 AM | 1:50–2:00 PM | 10:30 AM–2:00 PM | 48% | $6,254 | 25% |

> **put-then-call**, handoff **10:30 AM** · overlap **0 min** · gap between legs: back-to-back (handoff, no gap) · **combined $11,114**.

### MSFT

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 9:50–9:55 AM | 11:05–11:25 AM | 9:50 AM–11:25 AM | 44% | $2,088 | 34% |
| CALL | 3:45–3:50 PM | 3:55–4:00 PM | 3:45 PM–4:00 PM | 37% | $3,596 | 41% |

> **put-then-call**, handoff **11:25 AM** · overlap **0 min** · gap between legs: **260 min flat** (11:25 AM–3:45 PM) · **combined $5,684**.

### AAPL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 10:10–10:25 AM | 12:05–12:20 PM | 10:10 AM–12:20 PM | 43% | $3,053 | 51% |
| CALL | 3:40–3:45 PM | 3:55–4:00 PM | 3:40 PM–4:00 PM | 38% | $2,287 | 32% |

> **put-then-call**, handoff **12:20 PM** · overlap **0 min** · gap between legs: **200 min flat** (12:20 PM–3:40 PM) · **combined $5,340**.

### AMZN

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| PUT | 10:20–10:25 AM | 10:30–10:35 AM | 10:20 AM–10:35 AM | 54% | $842 | 22% |
| CALL | 10:50–11:00 AM | 11:50 AM–12:10 PM | 10:50 AM–12:10 PM | 44% | $1,921 | 29% |

> **put-then-call**, handoff **10:35 AM** · overlap **0 min** · gap between legs: **15 min flat** (10:35 AM–10:50 AM) · **combined $2,763**.

### ORCL

| Type | Entry window | Exit window | Hold window (entry→exit) | Win% | Total P&L | Top‑trade share |
|---|---|---|---|--:|--:|--:|
| CALL | 10:25–10:30 AM | 10:40–10:50 AM | 10:25 AM–10:50 AM | 54% | $2,308 | 17% |
| PUT | 10:55–11:00 AM | 2:55–3:00 PM | 10:55 AM–3:00 PM | 46% | $4,174 | 33% |

> **call-then-put**, handoff **10:50 AM** · overlap **0 min** · gap between legs: **5 min flat** (10:50 AM–10:55 AM) · **combined $6,482**.

