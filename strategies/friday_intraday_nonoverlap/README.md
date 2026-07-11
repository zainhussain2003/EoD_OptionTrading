# strategy/friday_intraday_nonoverlap — Friday 0DTE, non-overlapping call+put per equity

You want to trade **both** a call and a put on the same equity each Friday — but
being long a call *and* a put at the same instant makes no intuitive sense
(opposite deltas partly cancel, and you pay theta on both). This strategy fixes
that: per equity it jointly chooses a **call window** and a **put window** whose
**hold times do not overlap** — one leg fully exits before the other enters.

Built on `strategies/friday_intraday_concentration_capped/`; same seven names:

> **TSLA · AMZN · AAPL · NVDA · GOOGL · MSFT · ORCL** — 0DTE, full 9:30 AM–4:00 PM ET session.

## The pairing rule

Each leg's **hold window** is `[entry_start, exit_end]`. Two legs are
non-overlapping iff one's hold window ends at/before the other's begins — the day
splits at a single **handoff time** into a segment for one leg and a segment for
the other. So you get schedules like:

```
PUT  10:00–10:45   (bet down early)   →   CALL 10:45–2:10   (bet up after)
```

which is exactly the "it dips, *then* it runs" shape — never both at once.

**Selection:** among all frame pairs with **positive** net P&L for each leg, pick
the non-overlapping (call, put) combination that maximizes the **sum of the two
legs' `win_rate × avg_payoff`** (the same expected-profit metric the engine ranks
single legs by). Both orderings are considered — *put-then-call* and
*call-then-put* — and the better one wins. An efficient prefix/suffix
best-by-boundary sweep makes this O(N log N), not a brute-force O(N²) join.

If no non-overlapping pair exists where **both** legs are profitable, that equity
is reported `viable: false` (honest — sometimes only one side has an edge).

## Two passes (both reported)

| Pass | Candidate frames | Meaning |
|------|------------------|---------|
| **1 — without cap** | all frames | best non-overlapping pair, unconstrained |
| **2 — with concentration cap** | only frames whose biggest single win ≤ **51%** of that frame's net total P&L | best non-overlapping pair whose edge isn't one-jackpot luck |

`metrics.json → nonoverlap_pairs` carries pass 1; `metrics.json →
concentration_capped.nonoverlap_pairs` carries pass 2. The per-leg **independent**
optimum (`legs`, which may overlap) is kept alongside so you can compare the
non-overlapping schedule against the naive one.

## What each pair reports

Per equity: `order` (put-then-call / call-then-put), `handoff_time`, and for each
leg the `entry_frame`, `exit_frame`, `win_rate`, `total_pnl`, and
`single_trade_share`; plus `combined_pnl` and `overlap_minutes` (always 0).

## Output contract

`strategy.py` writes to `STRATEGY_RESULTS_DIR` (default `./output`):

- `metrics.json` — `nonoverlap_pairs` (pass 1) + `concentration_capped.nonoverlap_pairs`
  (pass 2), plus the independent per-leg `legs` for comparison (**required**)
- `trades.csv` / `trades_concentration_capped.csv` — per-leg ledgers
- `equity_curve.png`
- rich `backtest_friday_intraday_nonoverlap_<ticker>_<type>_*` `.csv`/`.txt` tables

and prints the `===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add ALPACA_API_KEY + ALPACA_SECRET_KEY for real data
python strategy.py            # pipeline artifacts + the paired summary
python backtest_timeframe.py  # full per-leg terminal report (heatmaps, top pairs)
```

Knobs at the top of `backtest_timeframe.py`:

```python
LOOKBACK_DAYS          = 730     # calendar days to test
TARGET_SPEND           = 1.00    # minimum premium per share ($1.00 = ~$100/trade)
MAX_SINGLE_TRADE_SHARE = 0.51    # pass-2 concentration cap
```

## Notes & caveats

- The paired windows are on the **coarse 5-minute grid** (the per-leg 1-minute
  refine still runs for the independent `legs`); 5-minute resolution is plenty
  for choosing non-overlapping segments.
- Each leg's P&L is still measured as if traded **in isolation** across all
  Fridays; the combined figure is their sum. Running both is a portfolio choice —
  this shows what the de-conflicted pair would have made, not a guarantee.
- Data: **Alpaca** real 0DTE option bars when keys are set; otherwise a
  Black-Scholes fallback.

> **Disclaimer:** For research/education. Not financial advice. Past
> performance does not guarantee future results.
