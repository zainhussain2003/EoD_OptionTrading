"""
core/report.py — human-readable summary.md builder.

Pulls the top findings out of the computed tables:
  - best entry window per symbol/direction for +50% and +100% on `market` fills
  - the mid-vs-market hit% gap by moneyness
  - how far the exit window (last_hold) stays open vs when the peak lands (mfe_min)
  - Mode B opportunity counts (labelled HINDSIGHT)
  - Mode C positive out-of-sample `market` expectancy combos
  - the validation report
  - ORCL/AMD noted separately (multi-day holds, not 0DTE)
"""
from __future__ import annotations

import pandas as pd


def _fmt(x, nd=1):
    try:
        if x is None or pd.isna(x):
            return "—"
        return f"{x:.{nd}f}"
    except Exception:
        return str(x)


def build_summary_md(ctx: dict) -> str:
    cfg = ctx["cfg"]
    L = []
    L.append("# Mon/Wed/Fri 0DTE option threshold-timing — summary\n")
    L.append("- **Scope:** TRUE 0DTE only (same-day expiry), Mon/Wed/Fri, no bridges. "
             "Lookback: Friday 730d · Mon/Wed 150d.")
    L.append(f"- **Data source:** {ctx['source_label']}")
    L.append(f"- **Date range covered:** {ctx['date_min']} → {ctx['date_max']} "
             f"({ctx['n_sessions']} sessions)")
    L.append(f"- **Universe:** {', '.join(cfg.tickers)}")
    L.append(f"- **Fill modes:** {', '.join(cfg.fill_modes)}  ·  "
             f"**Thresholds:** {', '.join(str(t) for t in cfg.thresholds_pct)}%")
    L.append(f"- **Entry sweep:** every {cfg.entry_step_min}m, "
             f"{cfg.entry_start_min//60:02d}:{cfg.entry_start_min%60:02d}–"
             f"{cfg.entry_end_min//60:02d}:{cfg.entry_end_min%60:02d} ET\n")
    if ctx["source_label"].startswith("SIMULATED"):
        L.append("> ⚠️ **SIMULATED fallback data — NOT a real edge.** Alpaca "
                 "credentials/quotes were unavailable, so these numbers exercise the "
                 "pipeline on Black-Scholes synthetic quotes only. Re-run on the "
                 "self-hosted runner for real results.\n")

    # ── Best entry window per symbol/direction for +50% and +100% (market) ───
    oe = ctx["optimal_entry"]
    L.append("## Best entry window (market fills) — +50% and +100%\n")
    if oe is not None and not oe.empty:
        mk = oe[oe["fill_mode"] == "market"]
        for T in (50, 100):
            L.append(f"### +{T}%")
            sub = mk[(mk["T_pct"] == T) & (mk["rank"] == 1)]
            if sub.empty:
                L.append("_no qualifying buckets_\n")
                continue
            L.append("| symbol | direction | regime | entry window | hit% | median min→target | n |")
            L.append("|---|---|---|---|---|---|---|")
            for _, r in sub.sort_values(["symbol", "direction"]).iterrows():
                flag = " ⚠️low-n" if r["low_sample"] else ""
                L.append(f"| {r['symbol']} | {r['direction']} | {r['regime']} | "
                         f"{r['entry_bucket']} | {_fmt(r['hit_pct'])}{flag} | "
                         f"{_fmt(r['median_min_to_target'])} | {int(r['n'])} |")
            L.append("")
    else:
        L.append("_no optimal-entry surface produced_\n")

    # ── mid-vs-market hit% gap by moneyness ──────────────────────────────────
    L.append("## mid − market hit% gap by moneyness (the spread's bite)\n")
    b = ctx["bucketed"]
    if b is not None and not b.empty:
        g = b.pivot_table(index="moneyness", columns="fill_mode", values="hit_pct",
                          aggfunc="mean")
        if "mid" in g.columns and "market" in g.columns:
            g["gap"] = g["mid"] - g["market"]
            L.append("| moneyness | mid hit% | market hit% | gap |")
            L.append("|---|---|---|---|")
            for mny in ["ITM", "ATM", "OTM1", "OTM2+"]:
                if mny in g.index:
                    L.append(f"| {mny} | {_fmt(g.loc[mny,'mid'])} | "
                             f"{_fmt(g.loc[mny,'market'])} | {_fmt(g.loc[mny,'gap'])} |")
            L.append("")

    # ── exit window (last_hold) vs peak timing (mfe_min) ─────────────────────
    L.append("## Exit window vs peak timing — market fills\n")
    if b is not None and not b.empty:
        mk = b[(b["fill_mode"] == "market") & (b["T_pct"].isin([30, 50]))]
        if not mk.empty:
            gg = mk.groupby(["symbol", "T_pct"]).agg(
                last_hold=("last_hold_median", "median"),
                mfe_min=("mfe_min_median", "median")).reset_index()
            L.append("Median minutes from entry: when the target's exit window "
                     "closes (`last_hold`) vs when the peak lands (`mfe_min`).\n")
            L.append("| symbol | T% | median last_hold (min) | median mfe_min (min) |")
            L.append("|---|---|---|---|")
            for _, r in gg.sort_values(["symbol", "T_pct"]).iterrows():
                L.append(f"| {r['symbol']} | {int(r['T_pct'])} | "
                         f"{_fmt(r['last_hold'])} | {_fmt(r['mfe_min'])} |")
            L.append("")

    # ── Mode B opportunity counts ────────────────────────────────────────────
    L.append("## Mode B — sequential non-overlapping OPPORTUNITIES per day "
             "(HINDSIGHT, not a live rule)\n")
    mb = ctx["mode_b_summary"]
    if mb is not None and not mb.empty:
        for T in cfg.highlight_pct:
            sub = mb[(mb["T_pct"] == T) & (mb["fill_mode"] == "market")
                     & (mb["moneyness"] == "ATM")]
            if sub.empty:
                continue
            L.append(f"### +{T}% (market, ATM)")
            L.append("| symbol | dir | mean trades/day | median | %days≥1 | %days≥2 | "
                     "%days≥3 | typ 1st | typ 2nd | typ 3rd |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            for _, r in sub.sort_values(["symbol", "direction"]).iterrows():
                L.append(f"| {r['symbol']} | {r['direction']} | "
                         f"{_fmt(r['mean_trades_per_day'],2)} | "
                         f"{_fmt(r['median_trades_per_day'],1)} | "
                         f"{_fmt(r['share_ge1']*100,0)}% | {_fmt(r['share_ge2']*100,0)}% | "
                         f"{_fmt(r['share_ge3']*100,0)}% | {r['typ_entry1']} | "
                         f"{r['typ_entry2']} | {r['typ_entry3']} |")
            L.append("")
    else:
        L.append("_no Mode B trades_\n")

    # ── Mode C positive out-of-sample market expectancy ──────────────────────
    L.append("## Mode C — positive OUT-OF-SAMPLE expectancy on `market` fills "
             "(the tradeable version)\n")
    perf = ctx["mode_c_perf"]
    if perf is not None and not perf.empty:
        pos = perf[(perf["fill_mode"] == "market")
                   & (perf["expectancy_per_trade"] > 0)].copy()
        if pos.empty:
            L.append("**None.** No (symbol, direction, moneyness, T) combo showed "
                     "positive out-of-sample `market` expectancy — on these data the "
                     "spread and forced-exit losses eat the edge.\n")
        else:
            pos = pos.sort_values("expectancy_per_day", ascending=False)
            L.append("Ranked by expectancy/day. `unreliable` = <"
                     f"{cfg.min_test_trades} test trades.\n")
            L.append("| symbol | dir | moneyness | T% | trades/day | win% | avg_loss | "
                     "exp/trade | exp/day | cum PnL | n |")
            L.append("|---|---|---|---|---|---|---|---|---|---|---|")
            for _, r in pos.iterrows():
                flag = " ⚠️" if r["unreliable_low_sample"] else ""
                L.append(f"| {r['symbol']} | {r['direction']} | {r['moneyness']} | "
                         f"{int(r['T_pct'])} | {_fmt(r['trades_per_day'],2)} | "
                         f"{_fmt(r['win_rate']*100,1)}% | {_fmt(r['avg_loss'],3)} | "
                         f"{_fmt(r['expectancy_per_trade'],4)} | "
                         f"{_fmt(r['expectancy_per_day'],4)}{flag} | "
                         f"{_fmt(r['cumulative_test_pnl'],3)} | {int(r['n_test_trades'])} |")
            L.append("")
        L.append("_Interpretation: positive `mid` but negative `market` = the spread "
                 "eats the edge; high win-rate with negative expectancy = occasional "
                 "−100% forced exits outweigh the +T% wins (the classic 0DTE trap)._\n")
    else:
        L.append("_no Mode C performance rows_\n")

    # ── ORCL / AMD note ──────────────────────────────────────────────────────
    L.append("## ORCL / AMD — Friday 0DTE only\n")
    L.append("ORCL and AMD list Friday weeklies only, so in this 0DTE-only study they "
             "contribute **Fri-0DTE sessions only** — they have no Mon/Wed same-day "
             "expiries, so those weekdays are simply absent for them (not bridged).\n")

    # ── Validation ───────────────────────────────────────────────────────────
    L.append("## Validation report\n")
    v = ctx["validation"]
    mm = v["mid_ge_market"]
    L.append(f"- **mid ≥ market gate:** {'PASS' if mm['ok'] else 'FAIL'} "
             f"({mm['n_compared']} instances compared, {len(mm['violations'])} "
             f"violation groups{': ' + str(mm['violations']) if mm['violations'] else ''})")
    L.append(f"- **regime detection:** {'PASS' if v['regimes']['ok'] else 'FAIL'} "
             f"{'' if v['regimes']['ok'] else v['regimes']['problems']}")
    L.append(f"- **no duplicate/overlapping instances:** "
             f"{'PASS' if v['no_overlap']['ok'] else 'FAIL'} "
             f"({v['no_overlap']['n_dupes']} dupes)")
    sc = v["spot_check"]
    L.append(f"- **hand spot-check ({sc['checked']} instances):** "
             f"{'PASS' if sc['ok'] else 'FAIL'} "
             f"{'' if sc['ok'] else sc['mismatches']}")
    L.append("")
    return "\n".join(L)
