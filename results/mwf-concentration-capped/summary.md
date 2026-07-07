I've written the failure summary to `results/mwf-concentration-capped/summary.md` (pending your write approval). Here is the complete summary content:

---

**Verdict: the strategy crashed with `KeyError: 'rows'` while aggregating metrics — the backtest itself finished, but `build_metrics` assumed every combo returned a `rows` list, and the combos that had no eligible schedule don't.**

### Error

```
KeyError: 'rows'
```

```
Traceback (most recent call last):
  File "strategies\mwf-concentration-capped\strategy.py", line 285, in main
    metrics = build_metrics(all_results, MAX_SINGLE_TRADE_SHARE, TARGET_SPEND)
  File "strategies\mwf-concentration-capped\strategy.py", line 194, in build_metrics
    all_rows.extend(res["rows"])
                    ~~~^^^^^^^^
KeyError: 'rows'
```

### Root-cause analysis

The backtest ran to completion — all 12 ticker/day/type combos were evaluated and printed. The crash is purely in the **post-processing** step. `run_concentration()` returns two shapes: a **chosen** combo with `"rows"` (`backtest_concentration.py:240`), and a **no-eligible-schedule** combo that is `base` + a `"reason"` key and has **no `"rows"`** (`:207`, `:231`). `build_metrics` guards only against an empty dict, not a missing key — so the `reason`-only dicts for **TSLA Monday CALLS** and **AAPL Monday CALLS** (both `cap_excluded_all`, per the log) crash `res["rows"]`. The cap did its job rejecting over-concentrated schedules; the aggregation just never handled the "nothing chosen" case.

### Suggested fixes

1. In `strategy.py:194`, change `if res:` → `if res and res.get("rows"):`.
2. Make `_combo_summary` (`strategy.py:196`) use `res.get(...)` so skipped combos summarise as `chosen: False` with their `skip_reason`.
3. Or, cleaner: add `"rows": []` to `base` in `backtest_concentration.py:201–203` so every result carries a list. Pick this **or** #1.
4. Add a regression assert that `len(all_rows) > 0` and `n_trades` matches the chosen combos.

---

The Write is blocked on a permission prompt — approve it and the summary lands on disk for Herald to pick up. Note: the existing file on disk currently holds a stale **success** summary (with a leading "I've written the summary…" preamble) from a prior run — this failure summary correctly replaces it.
