# EoD_OptionTrading — Thursday → Friday call probability

This branch answers one question:

> **If I buy the ATM weekly call the day before expiry between 3:55 and 3:59 PM
> ET, how often does it reach a given return target at _any point_ on the
> expiry day?**

For each entry minute (3:55, 3:56, 3:57, 3:58, 3:59), across every weekly pair
in the lookback window, it measures the option's **expiry-day session high** and
reports the probability that high hit each return target.

### Which days? (holiday-aware, no skipped weeks, no sim)

The weekly expiry is **Friday**, so you normally buy **Thursday**. But when that
Friday is a market holiday (e.g. **Good Friday**), the option expires
**Thursday** instead, so the entry rolls back to **Wednesday**:

| Week | Buy (entry) | Expiry / tracked day |
|------|-------------|----------------------|
| Normal | **Thursday** 3:55–3:59 PM | Friday |
| Friday closed | **Wednesday** 3:55–3:59 PM | Thursday |

This way no week is dropped and the holiday weeks stay on **real** data instead
of falling back to a simulated phantom-Friday. The market holidays are computed
from a built-in NYSE calendar (Good Friday, New Year, Juneteenth, July 4th,
Christmas, etc. — including weekend observation). The run summary reports how
many weeks were shifted, and the CSV tags each row with its entry/expiry
weekday.

## Return targets (profit ÷ premium paid)

Targets are **return multiples** of what you paid, so the price target scales
with the entry:

```
target_price = entry_price × (1 + multiple)
```

| Multiple | Price target | $0.50 entry → |
|----------|--------------|---------------|
| 1.0x     | × 2.00       | **$1.00** (double — money back + 100%) |
| 1.5x     | × 2.50       | $1.25 |
| 2.0x     | × 3.00       | $1.50 |
| 2.5x     | × 3.50       | $1.75 |

> **The math, checked:** "1x return" means **+100%** profit — a $0.50 option
> has to reach **$1.00**, as you described. (Note: this differs from a literal
> "1×/1.5×/2×/2.5× the _price_", where 1× would just be the entry price = always
> 100%.) Change `RETURN_MULTIPLES` at the top of the script if you want a
> different set, e.g. `[2, 3, 4, 5]` for "reach $1/$1.5/$2/$2.5 from $0.50".

### Which strike?

The call bought is the standard strike **at or above** the entry-day spot — the
ATM strike when spot sits exactly on one, otherwise the first strike **above**
it. It is never a strike below spot. Examples (with $2.50 strike spacing):

| Spot | Strike bought |
|------|---------------|
| 400.25 | **402.50** (first strike above) |
| 400.00 | **400.00** (exact ATM) |
| 401.00 | 402.50 |

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add ALPACA_API_KEY + ALPACA_API_SECRET for real data
python backtest_thu_fri_calls.py
```

Two knobs live at the very top of `backtest_thu_fri_calls.py`:

```python
LOOKBACK_DAYS    = 365                     # calendar days of history to test
RETURN_MULTIPLES = [1.0, 1.5, 2.0, 2.5]    # profit targets (× premium paid)
```

Output: two tables per ticker (and an all-tickers-combined view), saved as a
timestamped `.csv` (per-entry detail + summaries) and `.txt` (full tables)
under `thu_fri_results/`:

1. **TOUCH PROBABILITY** — for each entry minute, the chance the option's
   expiry-day *high* reached each target (best-case; a resting limit would
   fill on a touch).
2. **STRATEGY P&L** — a realistic backtest of trading it: rest a limit at the
   target; if it hasn't filled by **3:55 PM** on the expiry day, sell at
   3:55 PM at the market. Each cell shows the **average net $ per $100 staked**
   per trade and the **fill rate**, so you see the actual edge *including the
   losing weeks*, not just the upside. A filled limit credits exactly the
   target price (conservative on gap-ups); trading costs are not yet modelled
   (clean-edge view).

## Data source

- **Alpaca Markets** (`alpaca-py`) — real historical option bars. Used when
  `ALPACA_API_KEY` / `ALPACA_API_SECRET` are set. **Strongly preferred** — the
  "did it touch X" answer is only as good as the price path it's measured on.
- **yfinance + Black-Scholes** — automatic fallback that reconstructs option
  prices from the underlying's path and realized vol. Both legs of every
  sample (entry-day price and expiry-day path) always use the **same** source,
  so the return ratio is never real-vs-simulated.

The expiry-day high uses each bar's **high** (a true intraday touch), and the
"time to expiry" used in any simulation counts **regular trading hours only**
(overnight gaps and intervening holidays don't decay the option).

## Project layout

```
backtest_thu_fri_calls.py   entry script — edit the two knobs at the top
thu_fri_engine.py           engine: data collection, touch-probability, output
config.py                   tickers, risk-free rate
models.py                   dataclasses + data-source tags
utils/date_utils.py         Thu→Fri pairing, session windows, OCC symbols
utils/math_utils.py         Black-Scholes + realized vol
data/alpaca_fetcher.py      real option/stock bars (primary)
data/yf_fetcher.py          yfinance fallback
```

> **Disclaimer:** For research/education. Not financial advice. Past
> probabilities do not guarantee future results.
