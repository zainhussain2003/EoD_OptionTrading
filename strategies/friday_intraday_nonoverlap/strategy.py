#!/usr/bin/env python
"""
PIPELINE ADAPTER for the FRIDAY INTRADAY, NON-OVERLAPPING call+put study (0DTE
Friday-expiry weeklies across TSLA, AMZN, AAPL, NVDA, GOOGL, MSFT, ORCL).

The point of this variant: you want to trade BOTH a call and a put on the same
equity each Friday, but it makes no sense to be long a call and a put at the same
instant (opposite deltas, double theta). So per equity it jointly chooses a call
window and a put window whose HOLD TIMES DO NOT OVERLAP — one leg fully exits
before the other enters (e.g. put 10:00–10:45, then call 10:45–2:10) — maximizing
the sum of the two legs' win_rate × avg_payoff. `nonoverlap_pairs` in metrics.json
carries this per equity, for BOTH the unconstrained pass and the concentration-
capped pass (biggest single win <= MAX_SINGLE_TRADE_SHARE, default 51%, of a
frame's net total P&L). The per-leg independent optimum (`legs`) is kept alongside
for comparison against the overlapping version.

This is the entry point the EoD pipeline (Sentinel → Forge → Oracle → Herald)
runs. It wraps the standalone analysis in backtest_timeframe.py / timeframe_engine.py
and emits the pipeline's output contract:

  1. Reads Alpaca keys from env: ALPACA_API_KEY, ALPACA_SECRET_KEY.
  2. Writes all artifacts into STRATEGY_RESULTS_DIR (falls back to ./output):
       - metrics.json      machine-readable metrics  (REQUIRED)
       - trades.csv        per-Friday ledger (both calls and puts)
       - equity_curve.png  cumulative P&L chart
     plus the rich per-option-type *.txt / *.csv / *_concentration_capped.txt the
     standalone run produces (RESULTS_DIR is pointed at the same directory).
  3. Prints the ===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY=== block to stdout.
  4. Exits 0 on success; on error writes metrics.json {"status":"error"} and exits 1.

The actual research logic lives in timeframe_engine.py — this file only adapts it
to the pipeline. Run by hand with `python backtest_timeframe.py` for the full
terminal report, or `python strategy.py` to also produce the contract artifacts.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone as dt_timezone


def results_dir() -> str:
    """Where artifacts go. Pipeline sets STRATEGY_RESULTS_DIR; CLI uses ./output."""
    d = os.environ.get("STRATEGY_RESULTS_DIR", os.path.join(os.getcwd(), "output"))
    os.makedirs(d, exist_ok=True)
    return d


def _source_label(rows) -> str:
    srcs = {r["source"] for r in rows if r["pnl_dollars"] != ""}
    if "REAL" in srcs and "SIM" in srcs:
        return "MIXED real + Black-Scholes sim"
    if "REAL" in srcs:
        return "REAL Alpaca option bars"
    if "SIM" in srcs:
        return "SIMULATED (Black-Scholes)"
    return "NONE"


def _drawdown_and_sharpe(pnls):
    """Pure-Python max drawdown and a per-trade Sharpe (no numpy dependency)."""
    if not pnls:
        return 0.0, 0.0
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    n = len(pnls)
    mean = sum(pnls) / n
    if n > 1:
        var = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        std = var ** 0.5
        sharpe = (mean / std) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return round(max_dd, 2), round(sharpe, 3)


def _frame_summary(frame, summ, rows=None, ticker=None, opt_type=None):
    from timeframe_engine import frame_label
    data_source = _source_label(rows or [])
    label = {"ticker": ticker,
             "opt_type": ("CALL" if opt_type == "C" else "PUT") if opt_type else None}
    if frame is None:
        return {**label, "entry_frame": None, "exit_frame": None, "n_trades": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                "best_day": 0.0, "worst_day": 0.0,
                "return_on_spend": 0.0, "single_trade_share": None,
                "data_source": data_source}
    cost = summ.get("total_cost", 0.0)
    roi = (summ["total_pnl"] / cost) if cost else 0.0
    share = summ.get("single_trade_share")
    return {
        **label,
        "entry_frame": frame_label(frame["es"], frame["ee"]),
        "exit_frame": frame_label(frame["xs"], frame["xe"]),
        "entry_minutes": frame["ee"] - frame["es"],
        "exit_minutes": frame["xe"] - frame["xs"],
        "n_trades": summ["n"], "wins": summ["wins"],
        "win_rate": round(summ["win_rate"], 4),
        "total_pnl": round(summ["total_pnl"], 2),
        "avg_pnl": round(summ["avg_pnl"], 2),
        "best_day": round(summ["best"], 2), "worst_day": round(summ["worst"], 2),
        "premium_spent": round(cost, 2), "return_on_spend": round(roi, 4),
        # Biggest single winning trade as a share of this frame's total P&L —
        # the concentration figure the cap tests (None if total<=0 / no wins).
        "single_trade_share": (round(share, 4) if share is not None else None),
        "max_win": round(summ.get("max_win", 0.0), 2),
        "data_source": data_source,
    }


def _write_trades_csv(path, all_results, rows_getter):
    """Write a per-Friday ledger CSV. rows_getter(res) selects which row set
    (the unconstrained pass or the concentration-capped pass) to write."""
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "opt_type", "contract_symbol", "strike", "source",
                    "entry_frame", "entry_price", "exit_frame", "exit_price",
                    "payoff_per_share", "contracts", "cost_dollars",
                    "pnl_dollars", "profitable", "note"])
        for key, res in sorted(all_results.items(), key=lambda kv: kv[0][1]):
            if not res:
                continue
            for r in rows_getter(res):
                w.writerow([r["date"], r["opt_type"], r["contract_symbol"],
                            r["strike"], r["source"], r["entry_frame"],
                            r["entry_price"], r["exit_frame"], r["exit_price"],
                            r["payoff_per_share"], r["contracts"],
                            r["cost_dollars"], r["pnl_dollars"], r["profitable"],
                            r["note"]])


def save_artifacts(out_dir, all_results, has_capped=False):
    """trades.csv (combined ledger) + trades_concentration_capped.csv + equity_curve.png.

    trades_concentration_capped.csv mirrors trades.csv but uses the engine's
    concentration-capped pass: each leg re-optimized among frames whose biggest
    single winning trade is within the cap (same frames behind the
    *_concentration_capped.txt files). No trade is dropped between the two.
    """
    # Combined per-Friday ledger (unconstrained pass 1)
    _write_trades_csv(os.path.join(out_dir, "trades.csv"), all_results,
                      lambda res: res.get("rows", []))

    # Concentration-capped ledger (pass 2 — frames within the single-trade cap)
    if has_capped:
        _write_trades_csv(
            os.path.join(out_dir, "trades_concentration_capped.csv"), all_results,
            lambda res: (res.get("excl") or {}).get("rows", []))

    # equity_curve.png — one cumulative line per option type (chart is optional).
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        plotted = False
        for (ticker, opt_type), res in sorted(all_results.items(),
                                              key=lambda kv: kv[0][1]):
            if not res:
                continue
            pnls = [r["pnl_dollars"] for r in res["rows"] if r["pnl_dollars"] != ""]
            if not pnls:
                continue
            equity, cum = [], 0.0
            for p in pnls:
                cum += p
                equity.append(cum)
            label = f"{ticker} {'CALL' if opt_type == 'C' else 'PUT'}s"
            ax.plot(range(1, len(equity) + 1), equity, lw=1.8, label=label)
            plotted = True
        if plotted:
            ax.axhline(0, color="grey", lw=0.8, ls="--")
            ax.set_title("Cumulative P&L — Friday intraday optimal entry/exit "
                         "frames (0DTE, 7 names)")
            ax.set_xlabel("Trade # (Fridays)")
            ax.set_ylabel("Cumulative P&L ($)")
            ax.legend()
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "equity_curve.png"), dpi=110)
        plt.close(fig)
    except Exception as e:  # noqa: BLE001 - chart is nice-to-have, never fatal
        print(f"  [chart] skipped: {type(e).__name__}: {e}")


def _aggregate(all_rows):
    """Overall metrics over a flat list of per-day rows."""
    pnls = [r["pnl_dollars"] for r in all_rows if r["pnl_dollars"] != ""]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls)
    max_dd, sharpe = _drawdown_and_sharpe(pnls)
    return {
        "n_trades": n,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / n, 2) if n else 0.0,
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "data_source": _source_label(all_rows),
    }


def _pass_metrics(all_results, pass_key):
    """Build the {overall + per-leg} block for one pass.

    A leg is a (ticker × call/put) pair, keyed e.g. "AAPL_CALL" — so every
    ticker keeps its own optimal frames instead of one overwriting the other.

    pass_key=None  -> unconstrained pass 1:          res["rows"]/["frame"]/["summ"]
    pass_key="excl" -> concentration-capped pass 2:  res["excl"]["..."]
    """
    all_rows = []
    legs = {}
    for (ticker, opt_type), res in sorted(all_results.items()):
        src = (res or {}) if pass_key is None else (res or {}).get("excl") or {}
        rows = src.get("rows", []) if res else []
        all_rows.extend(rows)
        key = f"{ticker}_{'CALL' if opt_type == 'C' else 'PUT'}"
        legs[key] = _frame_summary(src.get("frame") if res else None,
                                   src.get("summ", {}) if res else {}, rows,
                                   ticker=ticker, opt_type=opt_type)
    block = _aggregate(all_rows)
    block["legs"] = legs
    return block


def _mmm(mn):
    """Minute-of-day -> '9:30 AM'."""
    h, m = mn // 60, mn % 60
    ap = "AM" if h < 12 else "PM"
    hh = h % 12 or 12
    return f"{hh}:{m:02d} {ap}"


def _leg_from_stat(stat, ticker, opt_type):
    """Format a ranked coarse frame-pair stat into a report leg dict."""
    from timeframe_engine import frame_label, CONTRACT_MULTIPLIER
    typ = "CALL" if opt_type == "C" else "PUT"
    if stat is None:
        return {"ticker": ticker, "opt_type": typ, "entry_frame": None,
                "exit_frame": None, "n_trades": 0, "win_rate": 0.0,
                "total_pnl": 0.0, "single_trade_share": None}
    share = stat.get("single_trade_share")
    return {
        "ticker": ticker, "opt_type": typ,
        "entry_frame": frame_label(stat["es"], stat["ee"]),
        "exit_frame": frame_label(stat["xs"], stat["xe"]),
        "hold_start_min": stat["es"], "hold_end_min": stat["xe"],
        "n_trades": stat["n"], "win_rate": round(stat["wr"], 4),
        "total_pnl": round(stat["total"] * CONTRACT_MULTIPLIER, 2),
        "single_trade_share": (round(share, 4) if share is not None else None),
    }


def _pair_nonoverlap(rc, rp, score_key, day_start, day_end, step=5):
    """Best NON-OVERLAPPING call+put pairing for one equity.

    rc / rp are the coarse ranked frame-pair stat lists for the call and put leg.
    A leg's occupied "hold window" is [es, xe] (entry-start → exit-end). Two legs
    are non-overlapping iff one's hold window ends at/before the other's begins,
    i.e. the day splits into two disjoint segments at some handoff time T.

    We only consider legs with positive net P&L (you want to actually make money
    on both), and maximize the sum of the two legs' expected-profit scores
    (win_rate × avg_payoff) — the same metric the engine ranks single legs by.
    A prefix/suffix best-by-boundary sweep makes this O(N log N), not O(N²).

    Returns {order, split, call, put} (stats) or None if no viable pair exists.
    """
    Cs = [s for s in rc if s.get("total", 0) > 0]
    Ps = [s for s in rp if s.get("total", 0) > 0]
    if not Cs or not Ps:
        return None
    Ts = list(range(day_start, day_end + 1, step))

    def prefix_by_end(pairs):
        """{T: best-scoring pair whose hold window ends at/before T}."""
        arr = sorted(pairs, key=lambda s: s["xe"])
        best, i, res = None, 0, {}
        for T in Ts:
            while i < len(arr) and arr[i]["xe"] <= T:
                if best is None or score_key(arr[i]) > score_key(best):
                    best = arr[i]
                i += 1
            res[T] = best
        return res

    def suffix_by_start(pairs):
        """{T: best-scoring pair whose hold window starts at/after T}."""
        arr = sorted(pairs, key=lambda s: s["es"], reverse=True)
        best, i, res = None, 0, {}
        for T in reversed(Ts):
            while i < len(arr) and arr[i]["es"] >= T:
                if best is None or score_key(arr[i]) > score_key(best):
                    best = arr[i]
                i += 1
            res[T] = best
        return res

    preC, sufP = prefix_by_end(Cs), suffix_by_start(Ps)
    preP, sufC = prefix_by_end(Ps), suffix_by_start(Cs)

    best = None  # (score, order, split, call_stat, put_stat)
    for T in Ts:
        c, p = preC.get(T), sufP.get(T)          # call finishes, then put
        if c and p:
            sc = score_key(c) + score_key(p)
            if best is None or sc > best[0]:
                best = (sc, "call-then-put", T, c, p)
        pp, cc = preP.get(T), sufC.get(T)         # put finishes, then call
        if pp and cc:
            sc = score_key(pp) + score_key(cc)
            if best is None or sc > best[0]:
                best = (sc, "put-then-call", T, cc, pp)
    if best is None:
        return None
    return {"order": best[1], "split": best[2], "call": best[3], "put": best[4]}


def _nonoverlap_pairs(all_results, pass_key, score_key, day_start, day_end):
    """Per-equity non-overlapping call+put schedules for one pass."""
    ranked, tickers = {}, []
    for (ticker, opt_type), res in all_results.items():
        if ticker not in tickers:
            tickers.append(ticker)
        src = (res or {}) if pass_key is None else (res or {}).get("excl") or {}
        ranked[(ticker, opt_type)] = src.get("ranked", []) if res else []

    pairs, combined_total = {}, 0.0
    for ticker in tickers:
        pr = _pair_nonoverlap(ranked.get((ticker, "C"), []),
                              ranked.get((ticker, "P"), []),
                              score_key, day_start, day_end)
        if pr is None:
            pairs[ticker] = {"ticker": ticker, "viable": False,
                             "note": "no non-overlapping call+put both with positive P&L"}
            continue
        call = _leg_from_stat(pr["call"], ticker, "C")
        put = _leg_from_stat(pr["put"], ticker, "P")
        cpnl = round(call["total_pnl"] + put["total_pnl"], 2)
        combined_total += cpnl
        pairs[ticker] = {
            "ticker": ticker, "viable": True, "order": pr["order"],
            "handoff_time": _mmm(pr["split"]), "overlap_minutes": 0,
            "call": call, "put": put, "combined_pnl": cpnl,
        }
    return {"pairs": pairs, "combined_pnl": round(combined_total, 2)}


def build_metrics(all_results, lookback_days, target_spend, cap_share, score_key):
    """Aggregate the per-option-type results into the contract metrics dict.

    Alongside the per-leg independent optimum (`legs`), each pass now carries a
    `nonoverlap_pairs` map: per equity, the best call window and put window whose
    hold times DO NOT overlap, so both can be traded on the same Friday without
    ever being long a call and a put simultaneously. Provided for both the
    unconstrained pass 1 and the concentration-capped pass 2.
    """
    import timeframe_engine as te
    ds, de = te.DAY_START_M, te.DAY_END_M

    normal = _pass_metrics(all_results, pass_key=None)
    pairs1 = _nonoverlap_pairs(all_results, None, score_key, ds, de)
    metrics = {
        "status": "ok",
        "strategy": "friday_intraday_nonoverlap",
        "tickers": ["TSLA", "AMZN", "AAPL", "NVDA", "GOOGL", "MSFT", "ORCL"],
        "entry_day": "Friday (intraday — buy and sell the same session)",
        "expiry": "Friday weekly (0DTE)",
        "session": "9:30 AM-4:00 PM ET",
        "lookback_days": lookback_days,
        "target_spend": target_spend,
        "max_single_trade_share": cap_share,
        "objective": (
            "per equity, jointly choose a call window and a put window whose hold "
            "times do NOT overlap (one leg fully exits before the other enters), "
            "maximizing the sum of the two legs' win_rate × avg_payoff"),
        "concentration_cap_rule": (
            "pass 2 restricts every candidate frame to biggest single winning "
            f"trade <= {cap_share:.0%} of its net total P&L (no trade dropped)"),
        **normal,
        "nonoverlap_pairs": pairs1["pairs"],
        "nonoverlap_combined_pnl": pairs1["combined_pnl"],
    }
    if cap_share is not None:
        excl = _pass_metrics(all_results, pass_key="excl")
        excl["max_single_trade_share"] = cap_share
        pairs2 = _nonoverlap_pairs(all_results, "excl", score_key, ds, de)
        excl["nonoverlap_pairs"] = pairs2["pairs"]
        excl["nonoverlap_combined_pnl"] = pairs2["combined_pnl"]
        metrics["concentration_capped"] = excl
    return metrics


def _print_pairs(title, pairs, combined):
    print(f"  {title}  (combined ${combined:,.0f})")
    for ticker, pr in pairs.items():
        if not pr.get("viable"):
            print(f"    {ticker:<6}: — no non-overlapping call+put both profitable")
            continue
        c, p = pr["call"], pr["put"]
        print(f"    {ticker:<6}: {pr['order']:<13} handoff {pr['handoff_time']:>8}  "
              f"combined ${pr['combined_pnl']:,.0f}")
        print(f"            CALL {str(c['entry_frame']):>15} → {str(c['exit_frame']):>15}"
              f"  (win {c['win_rate'] * 100:.0f}%, ${c['total_pnl']:,.0f})")
        print(f"            PUT  {str(p['entry_frame']):>15} → {str(p['exit_frame']):>15}"
              f"  (win {p['win_rate'] * 100:.0f}%, ${p['total_pnl']:,.0f})")


def print_summary(metrics):
    capped = metrics.get("concentration_capped") or {}
    cap = metrics.get("max_single_trade_share")
    cap_pct = f"{cap:.0%}" if cap is not None else "cap"
    print("\n" + "=" * 78)
    print("  STRATEGY SUMMARY — Friday intraday, NON-OVERLAPPING call+put pairs (7 names)")
    print("=" * 78)
    print(f"  Data source : {metrics.get('data_source')}")
    print("  Per equity: best call window + best put window whose HOLD TIMES DO NOT")
    print("  overlap (one leg fully exits before the other enters).")
    print()
    _print_pairs("WITHOUT concentration cap (pass 1):",
                 metrics.get("nonoverlap_pairs") or {},
                 metrics.get("nonoverlap_combined_pnl", 0))
    print()
    _print_pairs(f"WITH concentration cap (pass 2, single win <= {cap_pct}):",
                 capped.get("nonoverlap_pairs") or {},
                 capped.get("nonoverlap_combined_pnl", 0))
    print("=" * 78 + "\n")
    # Machine-readable block — Oracle / log scrapers key off these markers.
    print("===STRATEGY_SUMMARY_JSON===")
    print(json.dumps(metrics))
    print("===END_SUMMARY===")


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    out_dir = results_dir()

    # Surface data provenance up front (the engine also degrades gracefully).
    if not os.environ.get("ALPACA_API_KEY") or not (
            os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")):
        print("  [data] ALPACA_API_KEY / ALPACA_SECRET_KEY not set — results will "
              "fall back to Black-Scholes simulation (yfinance has no option bars).")

    try:
        import timeframe_engine as te
        from backtest_timeframe import (
            LOOKBACK_DAYS, TARGET_SPEND, MAX_SINGLE_TRADE_SHARE,
            size_fn, score_key, eligible, eligible_capped,
        )

        # Deliver the rich per-option-type TXT/CSV into the results dir too.
        te.RESULTS_DIR = out_dir

        all_results = te.run_timeframe(
            lookback_days=LOOKBACK_DAYS,
            method_label="MAX EXPECTED PROFIT, target-spend sized (win_rate × avg_payoff)",
            score_key=score_key,
            eligible=eligible,
            size_fn=size_fn,
            file_tag="friday_intraday_nonoverlap",
            eligible_capped=eligible_capped,
            cap_share=MAX_SINGLE_TRADE_SHARE,
            header_extra=(
                f"Position sizing: contracts = ceil(${TARGET_SPEND:.2f} / "
                f"mean(entry_frame)), min 1. Pass 2 concentration cap: biggest "
                f"single win <= {MAX_SINGLE_TRADE_SHARE:.0%} of net total P&L."
            ),
        )

        metrics = build_metrics(all_results, LOOKBACK_DAYS, TARGET_SPEND,
                                MAX_SINGLE_TRADE_SHARE, score_key)
        save_artifacts(out_dir, all_results, has_capped=True)
        metrics["generated_at"] = datetime.now(dt_timezone.utc).isoformat()
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print_summary(metrics)
        return 0

    except Exception as e:  # noqa: BLE001 - record the crash per the contract
        tb = traceback.format_exc()
        metrics = {"status": "error", "strategy": "friday_intraday_nonoverlap",
                   "error": f"{type(e).__name__}: {e}", "traceback": tb}
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(tb, file=sys.stderr)
        print("===STRATEGY_SUMMARY_JSON===")
        print(json.dumps(metrics))
        print("===END_SUMMARY===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
