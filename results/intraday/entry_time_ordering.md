# Intraday — suggested entry-time ordering, all weekdays

Source: `results/intraday/metrics.json` · data **MIXED real + Black-Scholes sim**. One row per **(equity, call/put)** = that day's single optimal intraday entry/exit window, ordered by **entry time** (market open first). This is the schedule the strategy *suggests* per day, not individual trades.

**Portfolio (all days):** 3611 trades · win 47.2% · total $296,778 · Sharpe 0.089 · max DD $-4,872.

| Day | Entry→Expiry | Lookback | Tickers | Trades | Win% | Total P&L | Real data |
|---|---|--:|--:|--:|--:|--:|--:|
| Monday | Mon→Monday (0DTE) | 150d | 6 | 213 | 56.8% | $34,820 | 100% |
| Tuesday | Tue→Wednesday (1DTE) | 150d | 6 | 246 | 63.4% | $14,960 | 96% |
| Wednesday | Wed→Wednesday (0DTE) | 150d | 6 | 224 | 57.1% | $24,488 | 95% |
| Thursday | Thu→Friday (1DTE) | 730d | 8 | 1492 | 51.6% | $52,708 | 100% |
| Friday | Fri→Friday (0DTE) | 730d | 8 | 1436 | 36.8% | $169,802 | 100% |

---

## Monday — Monday entry → Monday (0DTE)

Lookback **150d** · tickers **AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA** · 213 trades · win **56.8%** · total **$34,820** · real data **100%** (REAL Alpaca option bars).

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:31–9:36 AM | 3:31–3:36 PM | TSLA | PUT | 44% | 16 | $2,634 | REAL |
| 2 | 9:35–9:40 AM | 10:30–10:35 AM | NVDA | PUT | 55% | 20 | $610 | REAL |
| 3 | 9:35–9:40 AM | 3:55–4:00 PM | TSLA | CALL | 61% | 18 | $6,866 | REAL |
| 4 | 10:14–10:19 AM | 2:46–2:54 PM | GOOGL | CALL | 50% | 16 | $1,319 | REAL |
| 5 | 10:30–10:35 AM | 3:09–3:16 PM | NVDA | CALL | 55% | 20 | $1,968 | REAL |
| 6 | 11:42–11:50 AM | 1:11–1:18 PM | AAPL | PUT | 65% | 20 | $880 | REAL |
| 7 | 11:45–11:50 AM | 12:14–12:19 PM | AMZN | PUT | 55% | 20 | $884 | REAL |
| 8 | 1:50–1:55 PM | 3:52–3:57 PM | GOOGL | PUT | 82% | 11 | $2,310 | REAL |
| 9 | 2:36–2:42 PM | 3:11–3:16 PM | MSFT | PUT | 65% | 17 | $1,180 | REAL |
| 10 | 2:53–2:58 PM | 3:45–3:50 PM | AMZN | CALL | 50% | 18 | $8,941 | REAL |
| 11 | 3:10–3:17 PM | 3:53–4:00 PM | MSFT | CALL | 58% | 19 | $5,874 | REAL |
| 12 | 3:11–3:16 PM | 3:44–3:49 PM | AAPL | CALL | 50% | 18 | $1,356 | REAL |

## Tuesday — Tuesday entry → Wednesday (1DTE)

Lookback **150d** · tickers **AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA** · 246 trades · win **63.4%** · total **$14,960** · real data **96%** (MIXED real + Black-Scholes sim).

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:30–9:36 AM | 2:20–2:29 PM | AAPL | CALL | 67% | 21 | $1,669 | REAL |
| 2 | 9:30–9:35 AM | 11:19–11:30 AM | GOOGL | CALL | 76% | 21 | $1,192 | mixed |
| 3 | 9:32–9:58 AM | 12:30–12:35 PM | TSLA | PUT | 62% | 21 | $3,307 | mixed |
| 4 | 9:50–10:45 AM | 10:54 AM–12:45 PM | MSFT | PUT | 57% | 21 | $1,037 | mixed |
| 5 | 9:51–9:57 AM | 11:27–11:32 AM | NVDA | PUT | 57% | 21 | $1,228 | mixed |
| 6 | 10:39–10:44 AM | 11:28–11:35 AM | AMZN | PUT | 62% | 21 | $472 | mixed |
| 7 | 11:16–11:21 AM | 12:59–1:05 PM | GOOGL | PUT | 61% | 18 | $699 | mixed |
| 8 | 11:28–11:33 AM | 2:35–2:40 PM | NVDA | CALL | 67% | 21 | $1,307 | mixed |
| 9 | 11:30–11:35 AM | 1:40–1:45 PM | MSFT | CALL | 52% | 21 | $755 | mixed |
| 10 | 11:31–11:36 AM | 1:41–1:46 PM | AMZN | CALL | 68% | 19 | $867 | REAL |
| 11 | 12:32–12:37 PM | 3:42–3:47 PM | TSLA | CALL | 71% | 21 | $1,882 | mixed |
| 12 | 2:40–2:45 PM | 3:41–3:46 PM | AAPL | PUT | 60% | 20 | $545 | REAL |

## Wednesday — Wednesday entry → Wednesday (0DTE)

Lookback **150d** · tickers **AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA** · 224 trades · win **57.1%** · total **$24,488** · real data **95%** (MIXED real + Black-Scholes sim).

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:30–9:36 AM | 3:46–3:51 PM | MSFT | CALL | 59% | 17 | $2,055 | mixed |
| 2 | 9:42–9:47 AM | 1:48–2:28 PM | AMZN | CALL | 52% | 21 | $2,345 | REAL |
| 3 | 9:48–9:53 AM | 1:02–1:15 PM | AAPL | CALL | 57% | 21 | $2,850 | REAL |
| 4 | 9:48–9:53 AM | 11:00–11:05 AM | NVDA | CALL | 71% | 21 | $1,007 | mixed |
| 5 | 9:49–9:54 AM | 10:54–11:04 AM | TSLA | CALL | 62% | 21 | $2,452 | mixed |
| 6 | 9:51–10:03 AM | 3:36–3:43 PM | MSFT | PUT | 53% | 17 | $2,260 | mixed |
| 7 | 12:07–12:12 PM | 12:54–12:59 PM | NVDA | PUT | 52% | 21 | $1,004 | mixed |
| 8 | 12:23–12:29 PM | 3:55–4:00 PM | AMZN | PUT | 29% | 17 | $4,718 | mixed |
| 9 | 1:26–1:31 PM | 2:55–3:00 PM | TSLA | PUT | 65% | 20 | $1,651 | mixed |
| 10 | 2:05–2:10 PM | 2:29–2:35 PM | GOOGL | PUT | 73% | 15 | $953 | mixed |
| 11 | 2:16–2:23 PM | 3:23–3:28 PM | AAPL | PUT | 56% | 18 | $867 | REAL |
| 12 | 3:25–3:30 PM | 3:54–3:59 PM | GOOGL | CALL | 53% | 15 | $2,325 | mixed |

## Thursday — Thursday entry → Friday (1DTE)

Lookback **730d** · tickers **AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, AMD, ORCL** · 1492 trades · win **51.6%** · total **$52,708** · real data **100%** (REAL Alpaca option bars).

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:30–9:35 AM | 9:42–9:47 AM | AAPL | PUT | 52% | 98 | $2,082 | REAL |
| 2 | 9:30–9:35 AM | 9:44–9:49 AM | AMZN | PUT | 54% | 98 | $1,922 | REAL |
| 3 | 9:30–9:35 AM | 9:44–9:49 AM | GOOGL | PUT | 60% | 98 | $2,867 | REAL |
| 4 | 9:30–9:35 AM | 3:43–3:49 PM | NVDA | PUT | 40% | 97 | $3,093 | REAL |
| 5 | 9:31–9:36 AM | 3:15–3:25 PM | TSLA | PUT | 49% | 97 | $13,574 | REAL |
| 6 | 9:33–9:38 AM | 3:09–3:35 PM | AMD | PUT | 52% | 97 | $6,989 | REAL |
| 7 | 9:39–9:44 AM | 10:36–10:41 AM | NVDA | CALL | 46% | 98 | $1,323 | REAL |
| 8 | 9:40–9:45 AM | 10:56–11:21 AM | ORCL | CALL | 47% | 89 | $3,123 | REAL |
| 9 | 9:50–9:55 AM | 10:37–10:46 AM | MSFT | CALL | 50% | 98 | $1,256 | REAL |
| 10 | 9:55–10:12 AM | 1:30–1:36 PM | AAPL | CALL | 54% | 97 | $1,846 | REAL |
| 11 | 10:30–10:35 AM | 12:13–12:20 PM | AMZN | CALL | 55% | 98 | $1,983 | REAL |
| 12 | 10:43–10:48 AM | 1:05–1:12 PM | MSFT | PUT | 56% | 85 | $4,058 | REAL |
| 13 | 10:55–11:04 AM | 11:16–11:22 AM | AMD | CALL | 53% | 97 | $2,038 | REAL |
| 14 | 10:55–11:00 AM | 1:29–2:25 PM | GOOGL | CALL | 49% | 95 | $2,193 | REAL |
| 15 | 12:10–12:15 PM | 2:14–2:21 PM | ORCL | PUT | 62% | 53 | $2,396 | REAL |
| 16 | 12:31–12:36 PM | 1:00–1:15 PM | TSLA | CALL | 51% | 97 | $1,966 | REAL |

## Friday — Friday entry → Friday (0DTE)

Lookback **730d** · tickers **AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, AMD, ORCL** · 1436 trades · win **36.8%** · total **$169,802** · real data **100%** (REAL Alpaca option bars).

| # | Entry window | Exit window | Equity | Type | Win% | Trades | Total P&L | Src |
|--:|---|---|---|---|--:|--:|--:|:--:|
| 1 | 9:40–9:50 AM | 11:01–11:06 AM | MSFT | PUT | 44% | 99 | $3,334 | REAL |
| 2 | 9:40–9:45 AM | 1:45–1:54 PM | TSLA | CALL | 42% | 97 | $9,993 | REAL |
| 3 | 9:42–9:51 AM | 11:05–11:43 AM | GOOGL | PUT | 42% | 99 | $2,857 | REAL |
| 4 | 9:43–9:51 AM | 10:57–11:08 AM | AMZN | PUT | 43% | 99 | $3,746 | REAL |
| 5 | 10:00–10:05 AM | 12:04–12:10 PM | AAPL | PUT | 43% | 98 | $7,368 | REAL |
| 6 | 10:18–10:23 AM | 3:35–3:40 PM | AMD | PUT | 41% | 90 | $7,632 | REAL |
| 7 | 11:52–11:57 AM | 3:10–3:15 PM | ORCL | CALL | 22% | 64 | $5,471 | REAL |
| 8 | 2:35–2:40 PM | 3:55–4:00 PM | AMZN | CALL | 29% | 96 | $25,890 | REAL |
| 9 | 2:55–3:00 PM | 3:26–3:31 PM | ORCL | PUT | 43% | 53 | $25,666 | REAL |
| 10 | 3:06–3:11 PM | 3:55–4:00 PM | TSLA | PUT | 29% | 95 | $10,133 | REAL |
| 11 | 3:22–3:27 PM | 3:55–4:00 PM | AMD | CALL | 31% | 88 | $9,317 | REAL |
| 12 | 3:25–3:31 PM | 3:31–3:36 PM | NVDA | CALL | 26% | 97 | $10,587 | REAL |
| 13 | 3:32–3:37 PM | 3:55–4:00 PM | GOOGL | CALL | 43% | 86 | $34,128 | REAL |
| 14 | 3:44–3:49 PM | 3:54–4:00 PM | NVDA | PUT | 30% | 94 | $6,571 | REAL |
| 15 | 3:45–3:50 PM | 3:55–4:00 PM | MSFT | CALL | 37% | 87 | $3,569 | REAL |
| 16 | 3:50–3:55 PM | 3:55–4:00 PM | AAPL | CALL | 39% | 94 | $3,540 | REAL |

