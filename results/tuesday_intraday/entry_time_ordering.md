# Tuesday intraday — suggested entry-time ordering (Mag 7)

Source: `results/tuesday_intraday/metrics.json` · lookback **150 days** (~21 Tuesdays) · data **MIXED real + Black-Scholes sim**.

One row per **(equity, call/put)** — the strategy's single optimal intraday **entry window** and **exit window** on Tuesdays (trading the Wednesday-expiry option). This is the *schedule it suggests*, not individual trades. Src = REAL Alpaca bars / mixed / sim.

- **With outliers** = the primary optimized frames.
- **Without outliers** = re-optimized after dropping winning trades over $2,000 (robustness check).

---
## WITH outliers (primary)

### Chronological — each equity's suggested entry, ordered by entry time (open first)

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:30–9:36 AM | 2:20–2:29 PM | AAPL | CALL | 67% | 21 | $1,669 | REAL |
| 2 | 9:30–9:35 AM | 11:19–11:30 AM | GOOGL | CALL | 76% | 21 | $1,192 | mixed |
| 3 | 9:32–9:58 AM | 12:30–12:35 PM | TSLA | PUT | 62% | 21 | $3,307 | mixed |
| 4 | 9:43–9:54 AM | 10:57–11:05 AM | META | PUT | 71% | 21 | $1,393 | mixed |
| 5 | 9:50–10:45 AM | 10:54 AM–12:45 PM | MSFT | PUT | 57% | 21 | $1,037 | mixed |
| 6 | 9:51–9:57 AM | 11:27–11:32 AM | NVDA | PUT | 57% | 21 | $1,228 | mixed |
| 7 | 10:39–10:44 AM | 11:28–11:35 AM | AMZN | PUT | 62% | 21 | $472 | mixed |
| 8 | 11:16–11:21 AM | 12:59–1:05 PM | GOOGL | PUT | 61% | 18 | $699 | mixed |
| 9 | 11:28–11:33 AM | 2:35–2:40 PM | NVDA | CALL | 67% | 21 | $1,307 | mixed |
| 10 | 11:30–11:35 AM | 1:40–1:45 PM | MSFT | CALL | 52% | 21 | $755 | mixed |
| 11 | 11:31–11:36 AM | 1:41–1:46 PM | AMZN | CALL | 68% | 19 | $867 | REAL |
| 12 | 12:08–12:13 PM | 2:14–2:19 PM | META | CALL | 88% | 16 | $2,765 | mixed |
| 13 | 12:32–12:37 PM | 3:42–3:47 PM | TSLA | CALL | 71% | 21 | $1,882 | mixed |
| 14 | 2:40–2:45 PM | 3:41–3:46 PM | AAPL | PUT | 60% | 20 | $545 | REAL |

### By equity — call & put together (with overlap check)

### AAPL

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### GOOGL

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### TSLA

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### META

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### MSFT

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### NVDA

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### AMZN

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|


---

## WITHOUT outliers (re-optimized, winners > $2,000 dropped)

### Chronological — each equity's suggested entry, ordered by entry time (open first)

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:30–9:36 AM | 2:20–2:29 PM | AAPL | CALL | 67% | 21 | $1,669 | REAL |
| 2 | 9:30–9:35 AM | 11:19–11:30 AM | GOOGL | CALL | 76% | 21 | $1,192 | mixed |
| 3 | 9:37–9:55 AM | 12:14–12:19 PM | TSLA | PUT | 62% | 21 | $3,171 | mixed |
| 4 | 9:43–9:54 AM | 10:57–11:05 AM | META | PUT | 71% | 21 | $1,393 | mixed |
| 5 | 9:50–10:45 AM | 10:54 AM–12:45 PM | MSFT | PUT | 57% | 21 | $1,037 | mixed |
| 6 | 9:51–9:57 AM | 11:27–11:32 AM | NVDA | PUT | 57% | 21 | $1,228 | mixed |
| 7 | 10:39–10:44 AM | 11:28–11:35 AM | AMZN | PUT | 62% | 21 | $472 | mixed |
| 8 | 11:16–11:21 AM | 12:59–1:05 PM | GOOGL | PUT | 61% | 18 | $699 | mixed |
| 9 | 11:28–11:33 AM | 2:35–2:40 PM | NVDA | CALL | 67% | 21 | $1,307 | mixed |
| 10 | 11:30–11:35 AM | 1:40–1:45 PM | MSFT | CALL | 52% | 21 | $755 | mixed |
| 11 | 11:31–11:36 AM | 1:41–1:46 PM | AMZN | CALL | 68% | 19 | $867 | REAL |
| 12 | 12:08–12:13 PM | 2:14–2:19 PM | META | CALL | 88% | 16 | $2,765 | mixed |
| 13 | 12:32–12:37 PM | 3:42–3:47 PM | TSLA | CALL | 71% | 21 | $1,882 | mixed |
| 14 | 2:40–2:45 PM | 3:41–3:46 PM | AAPL | PUT | 60% | 20 | $545 | REAL |

### By equity — call & put together (with overlap check)

### AAPL

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### GOOGL

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### TSLA

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### META

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### MSFT

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### NVDA

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

### AMZN

| Type | Entry window | Exit window | Hold (entry→exit) | Win% | Total P&L | Src |
|---|---|---|---|--:|--:|:--:|

