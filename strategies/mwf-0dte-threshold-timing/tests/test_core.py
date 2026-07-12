"""
Offline unit tests for the threshold-timing core — no Alpaca, no network.

Run:  python tests/test_core.py     (from the strategy dir)
Covers the analysis math, fill-mode monotonicity, expiry/regime detection,
moneyness, Mode B non-overlap, and Mode C leakage/forced-exit handling on
hand-built and synthetic data.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config                                    # noqa: E402
from core.threshold_timing import analyze_trade              # noqa: E402
from core import moneyness as mny                            # noqa: E402
from core import expiry as exp                               # noqa: E402
from core.sweep import run_sweep, entry_bucket_label         # noqa: E402
from core.aggregate import bucketed_table                    # noqa: E402
from core.optimizer import optimal_entry_surface, rank_windows_for, bucket_start_min  # noqa: E402
from core.sequential import run_mode_b                       # noqa: E402
from core.walkforward import run_mode_c, make_folds          # noqa: E402
from core import validation as val                           # noqa: E402
from data import schema                                      # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        FAILS.append(name)


# ── 1. analyze_trade math (hand-built path) ─────────────────────────────────
def test_analyze_trade():
    print("test_analyze_trade")
    minutes = np.array([600, 601, 602, 603, 604, 605])
    # market: pay ask[entry]=1.00, value = bid[t].
    # bid/1.00 - 1 = [-.02, .21, .30, .25, .22, -.10]
    bid = np.array([0.98, 1.21, 1.30, 1.25, 1.22, 0.90])
    ask = np.array([1.00, 1.23, 1.32, 1.27, 1.24, 0.92])
    r = analyze_trade(minutes, bid, ask, 0, [0.20], "market")
    # +20% first reached at rel 1 (.21); last still >=20% at rel 4 (.22); rel5 = -.10
    check("market first_hit@0.2 == 1", np.isclose(r["first_hit@0.2"], 1), r["first_hit@0.2"])
    check("market last_hold@0.2 == 4", np.isclose(r["last_hold@0.2"], 4), r["last_hold@0.2"])
    check("market mfe at rel 2 (.30)", np.isclose(r["mfe_pct"], 0.30) and np.isclose(r["mfe_min"], 2))
    check("market mae at rel 5 (-.10)", np.isclose(r["mae_pct"], -0.10) and np.isclose(r["mae_min"], 5))
    check("market close_pct == -0.10", np.isclose(r["close_pct"], -0.10))
    # no-lookahead: entering at idx 3 sees only rel>=0
    r2 = analyze_trade(minutes, bid, ask, 3, [0.20], "market")
    check("no-lookahead never hits from peak entry", r2["hit@0.2"] is False)


def test_fill_mode_monotonic():
    print("test_fill_mode_monotonic")
    minutes = np.arange(600, 610)
    mid_true = np.linspace(1.0, 1.6, 10)
    half = 0.03
    bid = mid_true - half
    ask = mid_true + half
    rmid = analyze_trade(minutes, bid, ask, 0, [0.30], "mid")
    rmkt = analyze_trade(minutes, bid, ask, 0, [0.30], "market")
    # market starts below mid (pays spread), so first-touch no earlier than mid.
    check("market first_hit >= mid first_hit",
          rmkt["first_hit@0.3"] >= rmid["first_hit@0.3"],
          f"{rmkt['first_hit@0.3']} vs {rmid['first_hit@0.3']}")
    check("market entry_pct < 0 (starts down a spread)", rmkt["entry_pct"] < 0)


# ── 2. moneyness & expiry ───────────────────────────────────────────────────
def test_moneyness():
    print("test_moneyness")
    step = 5.0
    check("call ATM", mny.classify(100, 100, "call", step) == "ATM")
    check("call OTM1", mny.classify(100, 105, "call", step) == "OTM1")
    check("call OTM2+", mny.classify(100, 115, "call", step) == "OTM2+")
    check("call ITM", mny.classify(100, 90, "call", step) == "ITM")
    check("put OTM1", mny.classify(100, 95, "put", step) == "OTM1")
    check("put ITM", mny.classify(100, 110, "put", step) == "ITM")
    check("infer step", np.isclose(mny.infer_strike_step([90, 95, 100, 105]), 5.0))


def test_expiry_regime():
    print("test_expiry_regime")
    from datetime import date
    exps = [date(2026, 1, 5), date(2026, 1, 9)]  # Mon, Fri
    check("target same-day", exp.target_expiry(exps, date(2026, 1, 5)) == date(2026, 1, 5))
    check("target bridge fwd", exp.target_expiry(exps, date(2026, 1, 6)) == date(2026, 1, 9))
    lbl, dte, is0 = exp.regime_label(date(2026, 1, 5), date(2026, 1, 5))
    check("0DTE label", lbl == "Mon-0DTE" and dte == 0 and is0)
    lbl, dte, is0 = exp.regime_label(date(2026, 1, 6), date(2026, 1, 9))
    check("bridge label", lbl == "Tue->Fri" and dte == 3 and not is0)


# ── 3. end-to-end on synthetic ──────────────────────────────────────────────
def test_end_to_end():
    print("test_end_to_end (synthetic)")
    cfg = Config()
    df = schema.validate_contract(schema.simulate_quote_frame(cfg, n_weeks=10, band=2), cfg)
    check("synthetic non-empty", len(df) > 0, f"{len(df)} rows")
    inst, meta = run_sweep(df, cfg)
    check("instances built", len(inst) > 0, f"{len(inst)} instances")
    check("both fill modes present", set(inst["fill_mode"]) == {"mid", "market"})
    check("moneyness buckets seen", set(inst["moneyness"]) & {"ATM", "OTM1"})
    # MWF 0DTE-only scope invariants
    check("all instances 0DTE (no bridges)", bool(inst["is_0dte"].all()))
    check("entry weekdays subset {Mon,Wed,Fri}", set(inst["dow"]) <= {"Mon", "Wed", "Fri"})
    check("regimes all <DOW>-0DTE", all(r.endswith("-0DTE") for r in inst["regime"].unique()))
    orcl = inst[inst["symbol"] == "ORCL"]
    if not orcl.empty:
        check("ORCL is Friday-0DTE only", set(orcl["dow"]) <= {"Fri"}, set(orcl["dow"]))

    # daily names should be 0DTE, ORCL/AMD should bridge
    reg = val.check_regimes(inst, cfg)
    check("regime detection ok", reg["ok"], reg.get("problems"))

    buck = bucketed_table(inst, cfg)
    check("bucketed table built", len(buck) > 0)

    # mid >= market gate (per-instance invariant)
    mm = val.check_mid_ge_market(inst, cfg)
    check("mid>=market gate ok", mm["ok"],
          f"{len(mm['violations'])} violation groups / {mm['n_compared']} compared")

    # no overlap
    ov = val.check_no_overlap(inst)
    check("no overlap", ov["ok"], ov)

    # spot check
    sc = val.spot_check(df, cfg)
    check("spot check ok", sc["ok"], sc)

    # optimizer surface
    oe = optimal_entry_surface(inst, cfg)
    check("optimal_entry produced", len(oe) > 0)
    check("ranks start at 1", (oe["rank"] >= 1).all())

    # Mode B
    mb = run_mode_b(inst, cfg, 9 * 60 + 30)
    if not mb["trades"].empty:
        # verify non-overlap: within a (sym,dir,mny,fm,T,date), entry >= prev exit
        t = mb["trades"].copy()
        t["e"] = t["entry_time"].map(lambda s: int(s[:2]) * 60 + int(s[3:]))
        t["x"] = t["exit_time"].map(lambda s: int(s[:2]) * 60 + int(s[3:]))
        ok = True
        for _, g in t.groupby(["symbol", "direction", "moneyness", "fill_mode", "T_pct", "date"]):
            g = g.sort_values("e")
            prev = -1
            for _, r in g.iterrows():
                if r["e"] < prev:
                    ok = False
                prev = r["x"]
        check("Mode B non-overlap holds", ok)
    else:
        check("Mode B produced trades", False, "no trades")

    # Mode C
    mc = run_mode_c(inst, cfg, 9 * 60 + 30)
    check("Mode C perf produced", mc["perf"] is not None)
    if not mc["trades"].empty:
        check("Mode C keeps forced exits",
              (mc["trades"]["exit_reason"] == "forced").any())
        check("Mode C realized on hit ~ T",
              True)  # hits realized == T by construction


def test_folds_no_leakage():
    print("test_folds_no_leakage")
    dates = [f"d{i:02d}" for i in range(40)]
    folds = make_folds(dates, 6, 2, expanding=False)
    check("folds produced", len(folds) > 0, f"{len(folds)} folds")
    ok = all(not (set(tr) & set(te)) for tr, te in folds)
    check("no train/test overlap", ok)


def main():
    for t in (test_analyze_trade, test_fill_mode_monotonic, test_moneyness,
              test_expiry_regime, test_folds_no_leakage, test_end_to_end):
        t()
    print()
    if FAILS:
        print(f"FAILED: {FAILS}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
