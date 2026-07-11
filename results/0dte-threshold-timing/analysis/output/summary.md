# 0DTE / short-dated option threshold-timing — summary

- **Data source:** REAL Alpaca option bars (last-trade close) + modeled spread
- **Date range covered:** 2025-07-11 → 2026-07-10 (251 sessions)
- **Universe:** AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, ORCL, AMD
- **Fill modes:** mid, market  ·  **Thresholds:** 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100%
- **Entry sweep:** every 5m, 09:35–15:30 ET

## Best entry window (market fills) — +50% and +100%

### +50%
| symbol | direction | regime | entry window | hit% | median min→target | n |
|---|---|---|---|---|---|---|
| AAPL | call | Fri-0DTE | 09:30 | 31.5 | 41.5 | 1921 |
| AAPL | call | Mon->Fri | 09:30 | 22.8 | 82.5 | 1097 |
| AAPL | call | Tue->Fri | 09:30 | 15.6 | 90.0 | 1150 |
| AAPL | call | Wed->Fri | 09:30 | 18.6 | 73.0 | 1157 |
| AAPL | call | Thu->Fri | 09:30 | 24.5 | 104.0 | 1825 |
| AAPL | call | Mon-0DTE | 09:30 | 31.8 | 48.5 | 710 |
| AAPL | call | Tue->Wed | 09:30 | 39.9 | 81.0 | 770 |
| AAPL | call | Wed-0DTE | 09:30 | 42.7 | 42.0 | 784 |
| AAPL | call | Thu-0DTE | 09:30 | 71.9 | 43.0 | 114 |
| AAPL | call | Tue-0DTE | 13:30 | 11.1 ⚠️low-n | 30.0 | 18 |
| AAPL | put | Fri-0DTE | 11:00 | 29.6 | 75.0 | 1663 |
| AAPL | put | Mon->Fri | 10:00 | 21.3 | 136.0 | 1078 |
| AAPL | put | Tue->Fri | 10:00 | 16.8 | 204.0 | 1144 |
| AAPL | put | Wed->Fri | 10:30 | 26.7 | 78.0 | 1029 |
| AAPL | put | Thu->Fri | 09:30 | 28.9 | 77.0 | 1618 |
| AAPL | put | Mon-0DTE | 11:30 | 35.0 | 69.0 | 574 |
| AAPL | put | Tue->Wed | 09:30 | 23.4 | 49.0 | 757 |
| AAPL | put | Wed-0DTE | 13:30 | 31.2 | 60.0 | 506 |
| AAPL | put | Thu-0DTE | 11:00 | 21.8 | 26.0 | 101 |
| AAPL | put | Tue-0DTE | 14:30 | 53.8 ⚠️low-n | 18.0 | 13 |
| AMD | call | Fri-0DTE | 09:30 | 32.7 | 22.0 | 1847 |
| AMD | call | Mon->Fri | 09:30 | 17.0 | 69.0 | 1696 |
| AMD | call | Tue->Fri | 10:30 | 26.4 | 118.0 | 2001 |
| AMD | call | Wed->Fri | 09:30 | 33.7 | 42.5 | 1892 |
| AMD | call | Thu->Fri | 09:30 | 34.6 | 45.0 | 1757 |
| AMD | call | Mon->Thu | 11:00 | 39.7 | 92.5 | 131 |
| AMD | call | Tue->Thu | 09:30 | 47.4 | 132.5 | 114 |
| AMD | call | Wed->Thu | 09:30 | 61.4 | 74.5 | 127 |
| AMD | call | Thu-0DTE | 10:30 | 64.2 | 32.5 | 134 |
| AMD | put | Fri-0DTE | 10:00 | 43.8 | 33.0 | 1970 |
| AMD | put | Mon->Fri | 09:30 | 16.6 | 121.0 | 1542 |
| AMD | put | Tue->Fri | 09:30 | 22.3 | 54.0 | 1756 |
| AMD | put | Wed->Fri | 10:30 | 30.0 | 77.0 | 1754 |
| AMD | put | Thu->Fri | 09:30 | 42.7 | 43.0 | 1667 |
| AMD | put | Mon->Thu | 09:30 | 62.7 | 28.0 | 118 |
| AMD | put | Tue->Thu | 10:00 | 40.0 | 79.0 | 125 |
| AMD | put | Wed->Thu | 12:30 | 93.2 | 92.0 | 59 |
| AMD | put | Thu-0DTE | 11:00 | 47.0 | 25.0 | 100 |
| AMZN | call | Fri-0DTE | 09:30 | 25.3 | 42.5 | 1836 |
| AMZN | call | Mon->Fri | 10:00 | 11.5 | 87.0 | 1202 |
| AMZN | call | Tue->Fri | 09:30 | 22.8 | 81.0 | 1121 |
| AMZN | call | Wed->Fri | 10:30 | 15.8 | 104.0 | 1145 |
| AMZN | call | Thu->Fri | 09:30 | 32.3 | 107.5 | 1817 |
| AMZN | call | Mon-0DTE | 09:30 | 33.4 | 48.0 | 722 |
| AMZN | call | Tue->Wed | 10:00 | 37.2 | 66.5 | 802 |
| AMZN | call | Wed-0DTE | 09:30 | 34.3 | 49.0 | 743 |
| AMZN | call | Thu-0DTE | 09:30 | 82.6 | 33.0 | 109 |
| AMZN | call | Tue-0DTE | 13:30 | 75.0 ⚠️low-n | 104.0 | 20 |
| AMZN | put | Fri-0DTE | 10:30 | 28.8 | 70.0 | 1581 |
| AMZN | put | Mon->Fri | 09:30 | 11.5 | 70.0 | 957 |
| AMZN | put | Tue->Fri | 09:30 | 17.9 | 32.0 | 998 |
| AMZN | put | Wed->Fri | 09:30 | 25.0 | 110.0 | 975 |
| AMZN | put | Thu->Fri | 09:30 | 28.8 | 69.5 | 1589 |
| AMZN | put | Mon-0DTE | 11:30 | 31.5 | 70.0 | 543 |
| AMZN | put | Tue->Wed | 09:30 | 32.0 | 55.0 | 693 |
| AMZN | put | Wed-0DTE | 11:00 | 36.0 | 78.0 | 631 |
| AMZN | put | Thu-0DTE | 13:30 | 39.0 | 26.5 | 77 |
| AMZN | put | Tue-0DTE | 12:30 | 84.6 ⚠️low-n | 24.0 | 13 |
| GOOGL | call | Fri-0DTE | 09:30 | 34.1 | 47.0 | 1772 |
| GOOGL | call | Mon->Fri | 09:30 | 18.5 | 138.0 | 994 |
| GOOGL | call | Tue->Fri | 09:30 | 18.4 | 94.5 | 1172 |
| GOOGL | call | Wed->Fri | 09:30 | 26.9 | 41.0 | 1143 |
| GOOGL | call | Thu->Fri | 09:30 | 38.2 | 84.0 | 1670 |
| GOOGL | call | Mon-0DTE | 11:00 | 47.2 | 62.0 | 563 |
| GOOGL | call | Tue->Wed | 10:00 | 48.8 | 64.0 | 685 |
| GOOGL | call | Wed-0DTE | 09:30 | 40.1 | 27.0 | 653 |
| GOOGL | call | Thu-0DTE | 09:30 | 61.0 | 17.0 | 118 |
| GOOGL | call | Tue-0DTE | 09:30 | 100.0 ⚠️low-n | 19.0 | 29 |
| GOOGL | put | Fri-0DTE | 11:00 | 36.8 | 61.5 | 1266 |
| GOOGL | put | Mon->Fri | 10:00 | 19.5 | 123.0 | 954 |
| GOOGL | put | Tue->Fri | 10:00 | 20.3 | 60.0 | 1002 |
| GOOGL | put | Wed->Fri | 10:00 | 24.1 | 90.0 | 1029 |
| GOOGL | put | Thu->Fri | 09:30 | 39.6 | 49.0 | 1341 |
| GOOGL | put | Mon-0DTE | 12:30 | 33.1 | 102.5 | 356 |
| GOOGL | put | Tue->Wed | 09:30 | 40.2 | 43.0 | 559 |
| GOOGL | put | Wed-0DTE | 13:30 | 44.6 | 37.0 | 343 |
| GOOGL | put | Thu-0DTE | 10:30 | 35.9 | 18.0 | 103 |
| GOOGL | put | Tue-0DTE | 11:00 | 41.7 ⚠️low-n | 13.0 | 24 |
| META | call | Fri-0DTE | 09:30 | 34.3 | 30.0 | 1867 |
| META | call | Mon->Fri | 09:30 | 16.2 | 119.0 | 1029 |
| META | call | Tue->Fri | 09:30 | 21.7 | 178.0 | 1091 |
| META | call | Wed->Fri | 10:00 | 17.1 | 89.0 | 1231 |
| META | call | Thu->Fri | 09:30 | 38.2 | 64.0 | 1722 |
| META | call | Mon-0DTE | 09:30 | 43.8 | 66.0 | 715 |
| META | call | Tue->Wed | 10:00 | 43.2 | 110.0 | 767 |
| META | call | Wed-0DTE | 09:30 | 54.0 | 25.0 | 755 |
| META | call | Thu-0DTE | 09:30 | 52.5 | 17.0 | 118 |
| META | call | Tue-0DTE | 11:00 | 58.3 ⚠️low-n | 34.5 | 24 |
| META | put | Fri-0DTE | 09:30 | 45.1 | 30.0 | 1723 |
| META | put | Mon->Fri | 09:30 | 25.2 | 211.0 | 926 |
| META | put | Tue->Fri | 09:30 | 22.8 | 46.0 | 1004 |
| META | put | Wed->Fri | 09:30 | 30.8 | 106.0 | 978 |
| META | put | Thu->Fri | 09:30 | 40.0 | 45.5 | 1668 |
| META | put | Mon-0DTE | 14:30 | 39.1 | 29.5 | 389 |
| META | put | Tue->Wed | 09:30 | 43.8 | 50.0 | 704 |
| META | put | Wed-0DTE | 12:00 | 43.5 | 45.0 | 556 |
| META | put | Thu-0DTE | 13:00 | 42.3 | 50.5 | 71 |
| META | put | Tue-0DTE | 10:00 | 50.0 ⚠️low-n | 25.0 | 26 |
| MSFT | call | Fri-0DTE | 10:00 | 35.9 | 44.0 | 1994 |
| MSFT | call | Mon->Fri | 09:30 | 14.9 | 73.5 | 886 |
| MSFT | call | Tue->Fri | 09:30 | 23.4 | 163.5 | 1001 |
| MSFT | call | Wed->Fri | 10:00 | 24.4 | 71.5 | 1051 |
| MSFT | call | Thu->Fri | 10:00 | 29.2 | 72.0 | 1868 |
| MSFT | call | Mon-0DTE | 09:30 | 42.5 | 23.0 | 777 |
| MSFT | call | Tue->Wed | 09:30 | 22.0 | 34.0 | 803 |
| MSFT | call | Wed-0DTE | 09:30 | 46.8 | 28.0 | 861 |
| MSFT | call | Thu-0DTE | 09:30 | 89.0 | 37.0 | 109 |
| MSFT | call | Tue-0DTE | 09:30 | 66.7 | 26.5 | 33 |
| MSFT | put | Fri-0DTE | 09:30 | 39.8 | 24.0 | 1619 |
| MSFT | put | Mon->Fri | 09:30 | 13.8 | 91.0 | 787 |
| MSFT | put | Tue->Fri | 09:30 | 26.4 | 83.0 | 856 |
| MSFT | put | Wed->Fri | 10:30 | 35.1 | 58.0 | 772 |
| MSFT | put | Thu->Fri | 09:30 | 43.1 | 66.0 | 1505 |
| MSFT | put | Mon-0DTE | 10:30 | 44.3 | 42.0 | 693 |
| MSFT | put | Tue->Wed | 09:30 | 40.5 | 44.0 | 686 |
| MSFT | put | Wed-0DTE | 09:30 | 41.7 | 45.0 | 748 |
| MSFT | put | Thu-0DTE | 13:30 | 33.3 | 41.0 | 93 |
| MSFT | put | Tue-0DTE | 10:00 | 72.5 | 39.0 | 40 |
| NVDA | call | Fri-0DTE | 09:30 | 17.6 | 49.0 | 1913 |
| NVDA | call | Mon->Fri | 10:30 | 17.7 | 114.0 | 1166 |
| NVDA | call | Tue->Fri | 10:00 | 13.3 | 137.0 | 1424 |
| NVDA | call | Wed->Fri | 09:30 | 8.6 | 67.5 | 1214 |
| NVDA | call | Thu->Fri | 09:30 | 15.9 | 63.0 | 1786 |
| NVDA | call | Mon-0DTE | 10:00 | 31.0 | 85.0 | 738 |
| NVDA | call | Tue->Wed | 11:30 | 30.1 | 167.0 | 704 |
| NVDA | call | Wed-0DTE | 10:00 | 22.5 | 60.0 | 757 |
| NVDA | call | Thu-0DTE | 09:30 | 40.4 | 37.0 | 104 |
| NVDA | call | Tue-0DTE | 10:00 | 40.4 | 15.0 | 47 |
| NVDA | put | Fri-0DTE | 09:30 | 24.9 | 51.0 | 1769 |
| NVDA | put | Mon->Fri | 13:00 | 5.9 | 82.0 | 928 |
| NVDA | put | Tue->Fri | 09:30 | 17.7 | 80.0 | 1161 |
| NVDA | put | Wed->Fri | 09:30 | 21.4 | 117.0 | 1086 |
| NVDA | put | Thu->Fri | 09:30 | 30.0 | 52.0 | 1712 |
| NVDA | put | Mon-0DTE | 09:30 | 25.6 | 41.0 | 679 |
| NVDA | put | Tue->Wed | 10:00 | 39.0 | 50.0 | 756 |
| NVDA | put | Wed-0DTE | 12:00 | 32.1 | 87.0 | 539 |
| NVDA | put | Thu-0DTE | 10:30 | 20.2 | 50.0 | 94 |
| NVDA | put | Tue-0DTE | 10:30 | 81.0 | 22.0 | 42 |
| ORCL | call | Fri-0DTE | 10:00 | 34.1 | 35.5 | 1527 |
| ORCL | call | Mon->Fri | 09:30 | 21.7 | 64.0 | 1425 |
| ORCL | call | Tue->Fri | 11:00 | 14.8 | 126.0 | 1344 |
| ORCL | call | Wed->Fri | 09:30 | 23.2 | 73.0 | 1463 |
| ORCL | call | Thu->Fri | 09:30 | 34.0 | 37.0 | 1425 |
| ORCL | call | Mon->Thu | 09:30 | 23.7 | 24.0 | 97 |
| ORCL | call | Tue->Thu | 09:30 | 36.0 | 176.0 | 75 |
| ORCL | call | Wed->Thu | 09:30 | 4.6 | 10.0 | 65 |
| ORCL | call | Thu-0DTE | 09:30 | 47.7 | 36.0 | 65 |
| ORCL | put | Fri-0DTE | 09:30 | 41.0 | 26.5 | 1316 |
| ORCL | put | Mon->Fri | 09:30 | 15.3 | 166.0 | 1187 |
| ORCL | put | Tue->Fri | 09:30 | 34.7 | 69.0 | 1256 |
| ORCL | put | Wed->Fri | 10:00 | 32.5 | 120.0 | 1182 |
| ORCL | put | Thu->Fri | 09:30 | 37.3 | 61.0 | 1246 |
| ORCL | put | Mon->Thu | 09:30 | 26.5 | 13.5 | 68 |
| ORCL | put | Tue->Thu | 10:00 | 42.6 | 30.5 | 61 |
| ORCL | put | Wed->Thu | 11:00 | 71.9 | 246.0 | 32 |
| ORCL | put | Thu-0DTE | 10:00 | 27.3 | 20.0 | 44 |
| TSLA | call | Fri-0DTE | 09:30 | 44.9 | 23.0 | 2234 |
| TSLA | call | Mon->Fri | 09:30 | 27.3 | 100.0 | 1193 |
| TSLA | call | Tue->Fri | 09:30 | 18.2 | 154.0 | 1340 |
| TSLA | call | Wed->Fri | 09:30 | 37.6 | 160.0 | 1338 |
| TSLA | call | Thu->Fri | 10:30 | 29.8 | 68.0 | 2403 |
| TSLA | call | Mon-0DTE | 09:30 | 57.6 | 52.0 | 918 |
| TSLA | call | Tue->Wed | 10:00 | 38.9 | 99.0 | 1099 |
| TSLA | call | Wed-0DTE | 09:30 | 43.2 | 25.0 | 967 |
| TSLA | call | Thu-0DTE | 15:00 | 44.0 | 20.5 | 100 |
| TSLA | call | Tue-0DTE | 12:00 | 77.4 | 23.0 | 53 |
| TSLA | put | Fri-0DTE | 09:30 | 44.5 | 29.0 | 2214 |
| TSLA | put | Mon->Fri | 12:00 | 16.3 | 115.0 | 1285 |
| TSLA | put | Tue->Fri | 09:30 | 22.4 | 120.0 | 1326 |
| TSLA | put | Wed->Fri | 10:30 | 21.8 | 76.0 | 1498 |
| TSLA | put | Thu->Fri | 09:30 | 47.2 | 53.0 | 2019 |
| TSLA | put | Mon-0DTE | 10:00 | 43.4 | 44.0 | 1077 |
| TSLA | put | Tue->Wed | 09:30 | 49.0 | 48.0 | 940 |
| TSLA | put | Wed-0DTE | 09:30 | 45.5 | 24.0 | 975 |
| TSLA | put | Thu-0DTE | 09:30 | 79.2 | 45.0 | 130 |
| TSLA | put | Tue-0DTE | 11:00 | 80.0 | 39.0 | 50 |

### +100%
| symbol | direction | regime | entry window | hit% | median min→target | n |
|---|---|---|---|---|---|---|
| AAPL | call | Fri-0DTE | 09:30 | 20.2 | 64.5 | 1921 |
| AAPL | call | Mon->Fri | 10:00 | 8.0 | 104.0 | 1224 |
| AAPL | call | Tue->Fri | 09:30 | 4.7 | 71.5 | 1150 |
| AAPL | call | Wed->Fri | 09:30 | 7.5 | 103.0 | 1157 |
| AAPL | call | Thu->Fri | 09:30 | 10.1 | 103.0 | 1825 |
| AAPL | call | Mon-0DTE | 13:00 | 21.4 | 63.0 | 509 |
| AAPL | call | Tue->Wed | 09:30 | 26.0 | 163.5 | 770 |
| AAPL | call | Wed-0DTE | 09:30 | 30.1 | 88.5 | 784 |
| AAPL | call | Thu-0DTE | 09:30 | 49.1 | 51.0 | 114 |
| AAPL | call | Tue-0DTE | 09:30 | 0.0 | — | 36 |
| AAPL | put | Fri-0DTE | 10:00 | 18.1 | 76.0 | 1911 |
| AAPL | put | Mon->Fri | 10:00 | 6.7 | 250.5 | 1078 |
| AAPL | put | Tue->Fri | 13:00 | 5.2 | 127.0 | 851 |
| AAPL | put | Wed->Fri | 10:00 | 11.5 | 143.5 | 1128 |
| AAPL | put | Thu->Fri | 11:30 | 14.7 | 115.0 | 1538 |
| AAPL | put | Mon-0DTE | 11:30 | 22.1 | 110.0 | 574 |
| AAPL | put | Tue->Wed | 09:30 | 14.0 | 72.0 | 757 |
| AAPL | put | Wed-0DTE | 12:00 | 22.2 | 110.0 | 594 |
| AAPL | put | Thu-0DTE | 10:30 | 18.5 | 39.5 | 108 |
| AAPL | put | Tue-0DTE | 11:00 | 50.0 ⚠️low-n | 69.0 | 26 |
| AMD | call | Fri-0DTE | 09:30 | 17.4 | 29.0 | 1847 |
| AMD | call | Mon->Fri | 09:30 | 4.2 | 100.0 | 1696 |
| AMD | call | Tue->Fri | 10:30 | 6.4 | 186.0 | 2001 |
| AMD | call | Wed->Fri | 09:30 | 16.2 | 85.0 | 1892 |
| AMD | call | Thu->Fri | 09:30 | 18.4 | 100.0 | 1757 |
| AMD | call | Mon->Thu | 10:30 | 37.8 | 123.0 | 127 |
| AMD | call | Tue->Thu | 09:30 | 16.7 | 125.0 | 114 |
| AMD | call | Wed->Thu | 10:00 | 25.5 | 269.5 | 141 |
| AMD | call | Thu-0DTE | 09:30 | 52.0 | 14.0 | 127 |
| AMD | put | Fri-0DTE | 10:00 | 28.1 | 57.0 | 1970 |
| AMD | put | Mon->Fri | 09:30 | 1.3 | 285.5 | 1542 |
| AMD | put | Tue->Fri | 09:30 | 8.2 | 92.5 | 1756 |
| AMD | put | Wed->Fri | 09:30 | 11.3 | 72.0 | 1738 |
| AMD | put | Thu->Fri | 09:30 | 22.4 | 69.0 | 1667 |
| AMD | put | Mon->Thu | 09:30 | 44.1 | 150.0 | 118 |
| AMD | put | Tue->Thu | 09:30 | 30.4 | 120.0 | 112 |
| AMD | put | Wed->Thu | 12:00 | 42.5 | 130.5 | 80 |
| AMD | put | Thu-0DTE | 10:00 | 35.9 | 17.0 | 128 |
| AMZN | call | Fri-0DTE | 09:30 | 15.8 | 64.0 | 1836 |
| AMZN | call | Mon->Fri | 09:30 | 2.9 | 61.0 | 1066 |
| AMZN | call | Tue->Fri | 09:30 | 8.9 | 132.0 | 1121 |
| AMZN | call | Wed->Fri | 09:30 | 6.6 | 193.0 | 1111 |
| AMZN | call | Thu->Fri | 10:00 | 16.6 | 190.0 | 2072 |
| AMZN | call | Mon-0DTE | 09:30 | 21.1 | 68.5 | 722 |
| AMZN | call | Tue->Wed | 09:30 | 21.1 | 104.5 | 710 |
| AMZN | call | Wed-0DTE | 09:30 | 25.7 | 69.0 | 743 |
| AMZN | call | Thu-0DTE | 09:30 | 72.5 | 46.0 | 109 |
| AMZN | call | Tue-0DTE | 13:30 | 70.0 ⚠️low-n | 120.5 | 20 |
| AMZN | put | Fri-0DTE | 12:00 | 18.6 | 111.0 | 1294 |
| AMZN | put | Mon->Fri | 09:30 | 1.3 | 82.5 | 957 |
| AMZN | put | Tue->Fri | 09:30 | 6.3 | 171.0 | 998 |
| AMZN | put | Wed->Fri | 09:30 | 8.9 | 101.0 | 975 |
| AMZN | put | Thu->Fri | 10:00 | 13.9 | 101.0 | 1744 |
| AMZN | put | Mon-0DTE | 11:00 | 21.0 | 60.0 | 586 |
| AMZN | put | Tue->Wed | 09:30 | 16.3 | 68.0 | 693 |
| AMZN | put | Wed-0DTE | 10:30 | 24.7 | 64.0 | 669 |
| AMZN | put | Thu-0DTE | 13:30 | 23.4 | 37.0 | 77 |
| AMZN | put | Tue-0DTE | 10:00 | 76.9 ⚠️low-n | 20.0 | 26 |
| GOOGL | call | Fri-0DTE | 09:30 | 20.1 | 80.0 | 1772 |
| GOOGL | call | Mon->Fri | 09:30 | 4.1 | 107.0 | 994 |
| GOOGL | call | Tue->Fri | 10:30 | 6.0 | 135.0 | 1141 |
| GOOGL | call | Wed->Fri | 09:30 | 11.6 | 51.0 | 1143 |
| GOOGL | call | Thu->Fri | 10:00 | 21.9 | 182.0 | 1866 |
| GOOGL | call | Mon-0DTE | 09:30 | 29.5 | 46.0 | 675 |
| GOOGL | call | Tue->Wed | 09:30 | 31.0 | 86.0 | 635 |
| GOOGL | call | Wed-0DTE | 09:30 | 22.2 | 41.0 | 653 |
| GOOGL | call | Thu-0DTE | 09:30 | 56.8 | 28.0 | 118 |
| GOOGL | call | Tue-0DTE | 09:30 | 65.5 ⚠️low-n | 64.0 | 29 |
| GOOGL | put | Fri-0DTE | 11:00 | 22.8 | 92.0 | 1266 |
| GOOGL | put | Mon->Fri | 09:30 | 7.4 | 221.5 | 887 |
| GOOGL | put | Tue->Fri | 10:00 | 7.2 | 59.0 | 1002 |
| GOOGL | put | Wed->Fri | 11:00 | 11.4 | 87.0 | 884 |
| GOOGL | put | Thu->Fri | 09:30 | 19.8 | 79.0 | 1341 |
| GOOGL | put | Mon-0DTE | 12:00 | 24.1 | 162.5 | 423 |
| GOOGL | put | Tue->Wed | 11:00 | 25.5 | 109.5 | 525 |
| GOOGL | put | Wed-0DTE | 13:00 | 33.3 | 61.0 | 369 |
| GOOGL | put | Thu-0DTE | 10:30 | 31.1 | 30.5 | 103 |
| GOOGL | put | Tue-0DTE | 12:30 | 6.2 ⚠️low-n | 41.0 | 16 |
| META | call | Fri-0DTE | 09:30 | 20.1 | 41.0 | 1867 |
| META | call | Mon->Fri | 10:30 | 3.9 | 88.5 | 1036 |
| META | call | Tue->Fri | 11:30 | 8.4 | 178.0 | 959 |
| META | call | Wed->Fri | 10:00 | 7.2 | 125.0 | 1231 |
| META | call | Thu->Fri | 10:30 | 19.1 | 94.0 | 1778 |
| META | call | Mon-0DTE | 10:00 | 30.7 | 68.0 | 779 |
| META | call | Tue->Wed | 10:30 | 21.3 | 161.0 | 743 |
| META | call | Wed-0DTE | 09:30 | 41.5 | 41.0 | 755 |
| META | call | Thu-0DTE | 09:30 | 45.8 | 41.0 | 118 |
| META | call | Tue-0DTE | 15:00 | 35.7 ⚠️low-n | 44.0 | 14 |
| META | put | Fri-0DTE | 09:30 | 27.3 | 65.0 | 1723 |
| META | put | Mon->Fri | 09:30 | 9.4 | 277.0 | 926 |
| META | put | Tue->Fri | 09:30 | 5.7 | 60.0 | 1004 |
| META | put | Wed->Fri | 10:00 | 11.2 | 145.0 | 1014 |
| META | put | Thu->Fri | 10:00 | 20.1 | 124.5 | 1897 |
| META | put | Mon-0DTE | 14:30 | 27.2 | 37.0 | 389 |
| META | put | Tue->Wed | 09:30 | 18.3 | 50.0 | 704 |
| META | put | Wed-0DTE | 12:30 | 30.7 | 98.0 | 527 |
| META | put | Thu-0DTE | 13:00 | 26.8 | 59.0 | 71 |
| META | put | Tue-0DTE | 10:00 | 30.8 ⚠️low-n | 45.5 | 26 |
| MSFT | call | Fri-0DTE | 10:00 | 20.3 | 68.0 | 1994 |
| MSFT | call | Mon->Fri | 09:30 | 5.4 | 127.0 | 886 |
| MSFT | call | Tue->Fri | 10:00 | 9.5 | 152.0 | 1066 |
| MSFT | call | Wed->Fri | 10:00 | 12.1 | 96.0 | 1051 |
| MSFT | call | Thu->Fri | 10:00 | 13.3 | 110.0 | 1868 |
| MSFT | call | Mon-0DTE | 09:30 | 24.3 | 53.0 | 777 |
| MSFT | call | Tue->Wed | 11:00 | 11.3 | 117.5 | 817 |
| MSFT | call | Wed-0DTE | 09:30 | 34.7 | 43.0 | 861 |
| MSFT | call | Thu-0DTE | 09:30 | 72.5 | 48.0 | 109 |
| MSFT | call | Tue-0DTE | 13:30 | 41.4 ⚠️low-n | 34.5 | 29 |
| MSFT | put | Fri-0DTE | 09:30 | 25.3 | 50.0 | 1619 |
| MSFT | put | Mon->Fri | 12:00 | 2.5 | 182.0 | 524 |
| MSFT | put | Tue->Fri | 09:30 | 7.9 | 87.0 | 856 |
| MSFT | put | Wed->Fri | 10:00 | 19.8 | 139.5 | 870 |
| MSFT | put | Thu->Fri | 09:30 | 21.0 | 157.0 | 1505 |
| MSFT | put | Mon-0DTE | 10:30 | 31.0 | 72.0 | 693 |
| MSFT | put | Tue->Wed | 10:00 | 17.2 | 115.0 | 726 |
| MSFT | put | Wed-0DTE | 09:30 | 32.2 | 92.0 | 748 |
| MSFT | put | Thu-0DTE | 13:00 | 22.6 | 70.0 | 93 |
| MSFT | put | Tue-0DTE | 10:00 | 60.0 | 44.0 | 40 |
| NVDA | call | Fri-0DTE | 09:30 | 8.9 | 58.0 | 1913 |
| NVDA | call | Mon->Fri | 10:30 | 6.2 | 120.0 | 1166 |
| NVDA | call | Tue->Fri | 10:30 | 6.0 | 230.0 | 1373 |
| NVDA | call | Wed->Fri | 09:30 | 3.0 | 81.0 | 1214 |
| NVDA | call | Thu->Fri | 11:00 | 5.9 | 164.0 | 1931 |
| NVDA | call | Mon-0DTE | 10:00 | 18.7 | 135.0 | 738 |
| NVDA | call | Tue->Wed | 11:30 | 18.2 | 195.0 | 704 |
| NVDA | call | Wed-0DTE | 09:30 | 12.0 | 98.0 | 677 |
| NVDA | call | Thu-0DTE | 09:30 | 24.0 | 48.0 | 104 |
| NVDA | call | Tue-0DTE | 10:00 | 23.4 | 23.0 | 47 |
| NVDA | put | Fri-0DTE | 09:30 | 15.5 | 77.0 | 1769 |
| NVDA | put | Mon->Fri | 09:30 | 0.5 | 152.0 | 1010 |
| NVDA | put | Tue->Fri | 10:00 | 5.8 | 82.0 | 1286 |
| NVDA | put | Wed->Fri | 09:30 | 8.6 | 140.0 | 1086 |
| NVDA | put | Thu->Fri | 09:30 | 17.7 | 84.0 | 1712 |
| NVDA | put | Mon-0DTE | 10:00 | 15.5 | 30.0 | 716 |
| NVDA | put | Tue->Wed | 10:00 | 20.0 | 74.0 | 756 |
| NVDA | put | Wed-0DTE | 12:00 | 18.0 | 91.0 | 539 |
| NVDA | put | Thu-0DTE | 10:00 | 11.6 | 23.0 | 112 |
| NVDA | put | Tue-0DTE | 10:30 | 71.4 | 27.0 | 42 |
| ORCL | call | Fri-0DTE | 10:00 | 20.6 | 53.0 | 1527 |
| ORCL | call | Mon->Fri | 09:30 | 10.6 | 89.0 | 1425 |
| ORCL | call | Tue->Fri | 09:30 | 5.0 | 72.5 | 1511 |
| ORCL | call | Wed->Fri | 09:30 | 9.5 | 125.0 | 1463 |
| ORCL | call | Thu->Fri | 09:30 | 17.7 | 47.0 | 1425 |
| ORCL | call | Mon->Thu | 09:30 | 3.1 | 78.0 | 97 |
| ORCL | call | Tue->Thu | 11:30 | 18.9 | 106.0 | 53 |
| ORCL | call | Wed->Thu | 09:30 | 0.0 | — | 65 |
| ORCL | call | Thu-0DTE | 09:30 | 35.4 | 55.0 | 65 |
| ORCL | put | Fri-0DTE | 09:30 | 26.7 | 46.0 | 1316 |
| ORCL | put | Mon->Fri | 09:30 | 4.0 | 166.5 | 1187 |
| ORCL | put | Tue->Fri | 09:30 | 13.4 | 93.5 | 1256 |
| ORCL | put | Wed->Fri | 09:30 | 13.5 | 128.0 | 1206 |
| ORCL | put | Thu->Fri | 10:30 | 17.5 | 132.0 | 1142 |
| ORCL | put | Mon->Thu | 09:30 | 22.1 | 17.0 | 68 |
| ORCL | put | Tue->Thu | 10:00 | 9.8 | 28.0 | 61 |
| ORCL | put | Wed->Thu | 14:30 | 39.1 ⚠️low-n | 50.0 | 23 |
| ORCL | put | Thu-0DTE | 10:00 | 22.7 | 25.5 | 44 |
| TSLA | call | Fri-0DTE | 09:30 | 30.4 | 47.0 | 2234 |
| TSLA | call | Mon->Fri | 09:30 | 5.4 | 160.0 | 1193 |
| TSLA | call | Tue->Fri | 10:30 | 2.9 | 281.0 | 1558 |
| TSLA | call | Wed->Fri | 09:30 | 15.2 | 257.0 | 1338 |
| TSLA | call | Thu->Fri | 10:00 | 16.1 | 120.0 | 2461 |
| TSLA | call | Mon-0DTE | 09:30 | 45.6 | 90.0 | 918 |
| TSLA | call | Tue->Wed | 10:30 | 16.0 | 169.0 | 1076 |
| TSLA | call | Wed-0DTE | 09:30 | 30.2 | 41.0 | 967 |
| TSLA | call | Thu-0DTE | 15:00 | 38.0 | 29.0 | 100 |
| TSLA | call | Tue-0DTE | 12:00 | 56.6 | 34.5 | 53 |
| TSLA | put | Fri-0DTE | 09:30 | 29.6 | 40.0 | 2214 |
| TSLA | put | Mon->Fri | 11:30 | 4.5 | 175.0 | 1262 |
| TSLA | put | Tue->Fri | 10:00 | 6.0 | 171.0 | 1561 |
| TSLA | put | Wed->Fri | 09:30 | 9.1 | 87.0 | 1315 |
| TSLA | put | Thu->Fri | 09:30 | 25.1 | 90.0 | 2019 |
| TSLA | put | Mon-0DTE | 10:00 | 30.8 | 63.0 | 1077 |
| TSLA | put | Tue->Wed | 09:30 | 23.8 | 92.5 | 940 |
| TSLA | put | Wed-0DTE | 09:30 | 31.1 | 65.0 | 975 |
| TSLA | put | Thu-0DTE | 09:30 | 46.9 | 59.0 | 130 |
| TSLA | put | Tue-0DTE | 11:00 | 44.0 | 40.0 | 50 |

## mid − market hit% gap by moneyness (the spread's bite)

| moneyness | mid hit% | market hit% | gap |
|---|---|---|---|
| ITM | 18.1 | 16.4 | 1.7 |
| ATM | 33.9 | 29.5 | 4.4 |
| OTM1 | 32.3 | 23.5 | 8.8 |
| OTM2+ | 24.7 | 12.7 | 12.0 |

## Exit window vs peak timing — market fills

Median minutes from entry: when the target's exit window closes (`last_hold`) vs when the peak lands (`mfe_min`).

| symbol | T% | median last_hold (min) | median mfe_min (min) |
|---|---|---|---|
| AAPL | 30 | 176.5 | 41.0 |
| AAPL | 50 | 183.5 | 41.0 |
| AMD | 30 | 168.0 | 49.0 |
| AMD | 50 | 190.0 | 49.0 |
| AMZN | 30 | 171.0 | 47.0 |
| AMZN | 50 | 184.0 | 47.0 |
| GOOGL | 30 | 159.0 | 39.2 |
| GOOGL | 50 | 170.0 | 39.2 |
| META | 30 | 158.5 | 43.0 |
| META | 50 | 164.0 | 43.0 |
| MSFT | 30 | 154.0 | 44.2 |
| MSFT | 50 | 163.5 | 44.2 |
| NVDA | 30 | 166.5 | 34.0 |
| NVDA | 50 | 184.2 | 34.0 |
| ORCL | 30 | 176.5 | 42.0 |
| ORCL | 50 | 199.0 | 42.0 |
| TSLA | 30 | 163.0 | 49.0 |
| TSLA | 50 | 170.2 | 49.0 |

## Mode B — sequential non-overlapping OPPORTUNITIES per day (HINDSIGHT, not a live rule)

### +20% (market, ATM)
| symbol | dir | mean trades/day | median | %days≥1 | %days≥2 | %days≥3 | typ 1st | typ 2nd | typ 3rd |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | call | 4.01 | 3.0 | 100% | 84% | 63% | 09:35 | 10:15 | 11:00 |
| AAPL | put | 3.58 | 3.0 | 100% | 81% | 64% | 09:35 | 10:25 | 11:40 |
| AMD | call | 3.30 | 3.0 | 100% | 76% | 55% | 09:35 | 10:10 | 11:05 |
| AMD | put | 3.38 | 3.0 | 100% | 76% | 51% | 09:35 | 10:10 | 10:45 |
| AMZN | call | 3.82 | 3.0 | 100% | 83% | 62% | 09:35 | 10:15 | 11:10 |
| AMZN | put | 3.63 | 3.0 | 100% | 84% | 62% | 09:35 | 10:15 | 11:10 |
| GOOGL | call | 4.04 | 3.0 | 100% | 81% | 66% | 09:35 | 10:05 | 10:55 |
| GOOGL | put | 4.04 | 4.0 | 100% | 84% | 66% | 09:35 | 10:05 | 10:50 |
| META | call | 4.41 | 4.0 | 100% | 86% | 67% | 09:35 | 10:10 | 11:10 |
| META | put | 4.47 | 4.0 | 100% | 86% | 69% | 09:35 | 10:05 | 10:50 |
| MSFT | call | 4.24 | 3.0 | 100% | 85% | 66% | 09:35 | 10:05 | 10:45 |
| MSFT | put | 4.16 | 4.0 | 100% | 87% | 71% | 09:35 | 10:10 | 11:10 |
| NVDA | call | 3.37 | 3.0 | 100% | 77% | 56% | 09:35 | 10:15 | 11:20 |
| NVDA | put | 3.75 | 3.0 | 100% | 83% | 65% | 09:35 | 10:05 | 11:02 |
| ORCL | call | 3.23 | 2.0 | 100% | 76% | 48% | 09:35 | 10:12 | 10:40 |
| ORCL | put | 3.22 | 3.0 | 100% | 80% | 53% | 09:35 | 10:05 | 11:00 |
| TSLA | call | 4.34 | 3.0 | 100% | 86% | 66% | 09:35 | 10:10 | 10:55 |
| TSLA | put | 4.12 | 3.0 | 100% | 85% | 64% | 09:35 | 10:05 | 10:45 |

### +30% (market, ATM)
| symbol | dir | mean trades/day | median | %days≥1 | %days≥2 | %days≥3 | typ 1st | typ 2nd | typ 3rd |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | call | 3.08 | 2.0 | 100% | 70% | 49% | 09:35 | 10:25 | 11:10 |
| AAPL | put | 2.75 | 2.0 | 100% | 67% | 44% | 09:35 | 10:45 | 11:50 |
| AMD | call | 2.49 | 2.0 | 100% | 62% | 38% | 09:35 | 10:20 | 11:35 |
| AMD | put | 2.54 | 2.0 | 100% | 63% | 37% | 09:35 | 10:20 | 11:10 |
| AMZN | call | 2.98 | 2.0 | 100% | 71% | 50% | 09:35 | 10:35 | 11:50 |
| AMZN | put | 2.87 | 2.0 | 100% | 74% | 49% | 09:35 | 10:25 | 11:37 |
| GOOGL | call | 3.16 | 3.0 | 100% | 75% | 50% | 09:35 | 10:25 | 11:30 |
| GOOGL | put | 3.19 | 3.0 | 100% | 74% | 55% | 09:35 | 10:15 | 11:10 |
| META | call | 3.26 | 3.0 | 100% | 76% | 55% | 09:35 | 10:27 | 11:45 |
| META | put | 3.43 | 3.0 | 100% | 76% | 56% | 09:35 | 10:20 | 11:15 |
| MSFT | call | 3.26 | 3.0 | 100% | 76% | 53% | 09:35 | 10:20 | 11:05 |
| MSFT | put | 3.26 | 3.0 | 100% | 80% | 55% | 09:35 | 10:20 | 11:30 |
| NVDA | call | 2.68 | 2.0 | 100% | 68% | 44% | 09:35 | 10:35 | 12:00 |
| NVDA | put | 2.89 | 2.0 | 100% | 74% | 48% | 09:35 | 10:25 | 11:20 |
| ORCL | call | 2.49 | 2.0 | 100% | 63% | 36% | 09:35 | 10:30 | 11:20 |
| ORCL | put | 2.56 | 2.0 | 100% | 69% | 35% | 09:35 | 10:20 | 11:15 |
| TSLA | call | 3.37 | 3.0 | 100% | 78% | 52% | 09:35 | 10:25 | 11:15 |
| TSLA | put | 3.22 | 3.0 | 100% | 72% | 52% | 09:35 | 10:17 | 11:02 |

### +50% (market, ATM)
| symbol | dir | mean trades/day | median | %days≥1 | %days≥2 | %days≥3 | typ 1st | typ 2nd | typ 3rd |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | call | 2.35 | 2.0 | 100% | 60% | 36% | 09:35 | 10:40 | 12:30 |
| AAPL | put | 2.20 | 2.0 | 100% | 56% | 36% | 09:40 | 11:10 | 12:55 |
| AMD | call | 1.89 | 1.0 | 100% | 48% | 23% | 09:40 | 10:47 | 12:15 |
| AMD | put | 2.01 | 1.0 | 100% | 49% | 28% | 09:35 | 10:35 | 11:55 |
| AMZN | call | 2.30 | 2.0 | 100% | 58% | 37% | 09:35 | 11:10 | 12:35 |
| AMZN | put | 2.20 | 2.0 | 100% | 59% | 35% | 09:35 | 11:10 | 12:50 |
| GOOGL | call | 2.33 | 2.0 | 100% | 62% | 39% | 09:35 | 10:55 | 12:45 |
| GOOGL | put | 2.25 | 2.0 | 100% | 57% | 33% | 09:35 | 11:00 | 11:55 |
| META | call | 2.38 | 2.0 | 100% | 59% | 39% | 09:35 | 10:55 | 13:00 |
| META | put | 2.45 | 2.0 | 100% | 62% | 42% | 09:35 | 10:50 | 12:20 |
| MSFT | call | 2.32 | 2.0 | 100% | 59% | 37% | 09:35 | 10:35 | 11:45 |
| MSFT | put | 2.35 | 2.0 | 100% | 64% | 36% | 09:35 | 11:00 | 12:25 |
| NVDA | call | 1.98 | 2.0 | 100% | 51% | 30% | 09:35 | 11:27 | 13:25 |
| NVDA | put | 2.16 | 2.0 | 100% | 56% | 33% | 09:35 | 10:42 | 11:45 |
| ORCL | call | 1.90 | 1.0 | 100% | 46% | 23% | 09:35 | 10:35 | 11:50 |
| ORCL | put | 1.99 | 1.0 | 100% | 49% | 28% | 09:35 | 10:37 | 12:00 |
| TSLA | call | 2.50 | 2.0 | 100% | 63% | 39% | 09:35 | 10:55 | 12:45 |
| TSLA | put | 2.33 | 2.0 | 100% | 61% | 37% | 09:35 | 10:40 | 12:12 |

## Mode C — positive OUT-OF-SAMPLE expectancy on `market` fills (the tradeable version)

Ranked by expectancy/day. `unreliable` = <30 test trades.

| symbol | dir | moneyness | T% | trades/day | win% | avg_loss | exp/trade | exp/day | cum PnL | n |
|---|---|---|---|---|---|---|---|---|---|---|
| GOOGL | call | ITM | 100 | 1.13 | 11.7% | -0.105 | 0.0238 | 0.0268 | 5.930 | 249 |
| AAPL | call | ITM | 60 | 1.29 | 24.1% | -0.169 | 0.0164 | 0.0212 | 4.682 | 286 |
| AAPL | call | ITM | 90 | 1.13 | 12.0% | -0.106 | 0.0149 | 0.0167 | 3.700 | 249 |
| GOOGL | call | ITM | 75 | 1.24 | 20.4% | -0.176 | 0.0126 | 0.0156 | 3.451 | 275 |
| ORCL | put | ITM | 70 | 1.10 | 9.9% | -0.063 | 0.0127 | 0.0140 | 3.090 | 243 |
| AAPL | call | ITM | 80 | 1.17 | 16.3% | -0.142 | 0.0110 | 0.0128 | 2.832 | 258 |
| AAPL | call | ITM | 100 | 1.08 | 8.8% | -0.084 | 0.0114 | 0.0123 | 2.727 | 239 |
| GOOGL | call | ITM | 90 | 1.15 | 14.1% | -0.137 | 0.0091 | 0.0105 | 2.315 | 255 |
| AAPL | call | ITM | 75 | 1.20 | 18.1% | -0.155 | 0.0083 | 0.0100 | 2.222 | 266 |
| GOOGL | call | ITM | 70 | 1.25 | 22.7% | -0.200 | 0.0050 | 0.0063 | 1.392 | 277 |
| ORCL | put | ITM | 90 | 1.05 | 5.6% | -0.049 | 0.0044 | 0.0046 | 1.018 | 232 |
| ORCL | put | ITM | 100 | 1.03 | 3.5% | -0.033 | 0.0032 | 0.0033 | 0.731 | 228 |
| ORCL | put | ITM | 75 | 1.08 | 8.0% | -0.063 | 0.0022 | 0.0023 | 0.516 | 238 |
| AAPL | call | ITM | 50 | 1.36 | 27.9% | -0.192 | 0.0009 | 0.0012 | 0.262 | 301 |
| GOOGL | call | ITM | 80 | 1.18 | 16.5% | -0.158 | 0.0001 | 0.0002 | 0.039 | 261 |

_Interpretation: positive `mid` but negative `market` = the spread eats the edge; high win-rate with negative expectancy = occasional −100% forced exits outweigh the +T% wins (the classic 0DTE trap)._

## ORCL / AMD — multi-day holds, NOT 0DTE

ORCL and AMD list Friday weeklies only, so early-week entries bridge to Friday (labelled e.g. `Mon->Fri`, with days-to-expiry recorded). Their threshold timing reflects multi-day theta/vega dynamics and must not be compared directly with the true 0DTE names.

## Validation report

- **mid ≥ market gate:** PASS (1705121 instances compared, 0 violation groups)
- **regime detection:** FAIL ['AAPL: expected mostly 0DTE, saw 0.36', 'NVDA: expected mostly 0DTE, saw 0.35', 'AMZN: expected mostly 0DTE, saw 0.36', 'META: expected mostly 0DTE, saw 0.38', 'TSLA: expected mostly 0DTE, saw 0.38']
- **no duplicate/overlapping instances:** PASS (0 dupes)
- **hand spot-check (45 instances):** PASS 
