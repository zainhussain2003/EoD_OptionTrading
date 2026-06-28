#!/usr/bin/env python
"""
ORACLE — the analyst.

Source of truth for behavior: agents/oracle.md

Reads Forge's output for strategies/<name> and produces results/<name>/summary.md:
  - SUCCESS: a metrics summary (P&L, win rate, max drawdown, Sharpe, # trades)
    plus a short plain-English interpretation.
  - FAILURE: an analysis of the error with concrete suggested fixes.

By design it asks the local `claude` CLI (your subscription login) to write the
narrative, feeding it agents/oracle.md as instructions plus the raw metrics/log.
If `claude` is unavailable or errors, it falls back to a fully deterministic
template so the pipeline NEVER goes silent.

Usage:  python agents/_runner/oracle.py <strategy-name>
"""
from __future__ import annotations

import os
import sys
import json

from _pipeline_common import (
    repo_root, results_dir, read_metrics, have_claude, run_claude, log,
    strategy_name_from_branch,
)


def _read(path: str, limit: int | None = None) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        txt = f.read()
    if limit and len(txt) > limit:
        return txt[-limit:]
    return txt


def build_prompt(name, oracle_md, metrics, runlog_tail, succeeded) -> str:
    outcome = "SUCCEEDED" if succeeded else "FAILED"
    return f"""You are Oracle, the analyst agent in an automated option-trading pipeline.
Follow these instructions (your source of truth):

--- agents/oracle.md ---
{oracle_md}
--- end instructions ---

Strategy name: {name}
Outcome: the strategy {outcome}.

metrics.json:
```json
{json.dumps(metrics, indent=2)}
```

Tail of run.log:
```
{runlog_tail}
```

Write the COMPLETE contents of results/{name}/summary.md in GitHub-flavored
Markdown. Output ONLY the markdown (no preamble, no code fence around the whole
thing).

If the strategy SUCCEEDED, structure the body with these exact sections, in order:

### Results (With Outliers)
A metrics table broken out by Calls and Puts (columns: Metric | Calls | Puts),
with rows: Trades, Win rate, Total P&L, Avg P&L, Best trade, Worst trade,
Best entry → exit, Data source. Use the top-level metrics + the `calls`/`puts`
objects in metrics.json.

### Results (Without Outliers)
The SAME table, but built from the `outliers_removed` object in metrics.json
(its `calls`/`puts`). If `outliers_removed` is absent, say so in one line.

### Oracle's Verdict
A short analysis paragraph: is the edge real or noise? Compare the With vs
Without Outliers totals to judge how fat-tail-driven the result is, watch the
sample size and the data source (flag SIMULATED data as not tradeable).

If the strategy FAILED, lead with the error, a root-cause analysis, and a
numbered list of concrete suggested fixes."""


def _fmt_money(v) -> str:
    return f"${v:,.0f}" if isinstance(v, (int, float)) else "—"


def _fmt_pct(v) -> str:
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "—"


def _entry_exit(d) -> str:
    ef, xf = d.get("entry_frame"), d.get("exit_frame")
    return f"{ef} → {xf}" if ef and xf else "—"


def _calls_puts_table(block) -> str:
    """Calls/Puts metrics table for a single pass (with- or without-outliers)."""
    calls = block.get("calls") or {}
    puts = block.get("puts") or {}
    default_src = block.get("data_source") or "—"
    rows = [
        ("Trades", calls.get("n_trades"), puts.get("n_trades")),
        ("Win rate", _fmt_pct(calls.get("win_rate")), _fmt_pct(puts.get("win_rate"))),
        ("Total P&L", _fmt_money(calls.get("total_pnl")), _fmt_money(puts.get("total_pnl"))),
        ("Avg P&L", _fmt_money(calls.get("avg_pnl")), _fmt_money(puts.get("avg_pnl"))),
        ("Best trade", _fmt_money(calls.get("best_day")), _fmt_money(puts.get("best_day"))),
        ("Worst trade", _fmt_money(calls.get("worst_day")), _fmt_money(puts.get("worst_day"))),
        ("Best entry → exit", _entry_exit(calls), _entry_exit(puts)),
        ("Data source", calls.get("data_source") or default_src,
                        puts.get("data_source") or default_src),
    ]
    body = "\n".join(
        f"| {m} | {c if c is not None else '—'} | {p if p is not None else '—'} |"
        for m, c, p in rows
    )
    return "| Metric | Calls | Puts |\n|---|---|---|\n" + body


def _value_table(block) -> str:
    """Single-column metrics table for strategies without a calls/puts split."""
    rows = [
        ("Trades", block.get("n_trades")),
        ("Win rate", _fmt_pct(block.get("win_rate"))),
        ("Total P&L", _fmt_money(block.get("total_pnl"))),
        ("Avg P&L", _fmt_money(block.get("avg_pnl"))),
        ("Best trade", _fmt_money(block.get("best_trade"))),
        ("Worst trade", _fmt_money(block.get("worst_trade"))),
        ("Max drawdown", _fmt_money(block.get("max_drawdown"))),
        ("Sharpe", block.get("sharpe")),
        ("Data source", block.get("data_source")),
    ]
    body = "\n".join(f"| {k} | {v} |" for k, v in rows if v is not None)
    return "| Metric | Value |\n|---|---|\n" + body


def _section(block) -> str:
    """Render the right table for a metrics block (calls/puts if present)."""
    if not block:
        return "_No metrics available._"
    if block.get("calls") or block.get("puts"):
        return _calls_puts_table(block)
    return _value_table(block)


def _verdict(metrics) -> str:
    wo = metrics.get("outliers_removed") or {}
    total = metrics.get("total_pnl", 0) or 0
    parts = [
        f"The backtest produced {metrics.get('n_trades', 0)} trades with a "
        f"{metrics.get('win_rate', 0) * 100:.1f}% win rate and {_fmt_money(total)} "
        f"total P&L (with outliers)."
    ]
    if wo:
        total_wo = wo.get("total_pnl", 0) or 0
        parts.append(
            f"With winning trades above {_fmt_money(metrics.get('outlier_max'))} removed, "
            f"total P&L is {_fmt_money(total_wo)} ({wo.get('win_rate', 0) * 100:.1f}% win rate) "
            f"— a {_fmt_money(total - total_wo)} swing, so weigh how much of the edge is "
            f"fat-tail-driven before trusting it."
        )
    ds = (metrics.get("data_source") or "").upper()
    if "SIM" in ds:
        parts.append("Data is SIMULATED, not real option bars — treat this as a plumbing "
                     "check, not a tradeable conclusion.")
    parts.append("_(Deterministic summary — `claude` CLI was unavailable on the runner.)_")
    return " ".join(parts)


def deterministic_summary(name, metrics, runlog_tail, succeeded) -> str:
    if succeeded:
        without = metrics.get("outliers_removed")
        without_section = (
            _section(without) if without else
            "_This strategy did not emit an outliers-removed metrics set._"
        )
        return (f"# Oracle Summary — {name}\n\n"
                f"**Result: SUCCESS**\n\n"
                f"### Results (With Outliers)\n\n{_section(metrics)}\n\n"
                f"### Results (Without Outliers)\n\n{without_section}\n\n"
                f"### Oracle's Verdict\n\n{_verdict(metrics)}\n")
    error = metrics.get("error", "unknown error")
    tb = metrics.get("traceback", runlog_tail)
    return (f"# Oracle Summary — {name}\n\n"
            f"**Result: FAILURE**\n\n## Error\n\n```\n{error}\n```\n\n"
            f"## Traceback / log tail\n\n```\n{tb}\n```\n\n"
            f"## Suggested fixes\n\n"
            f"1. Re-read the traceback's last line — it names the failing call.\n"
            f"2. If it's an `ImportError`, add the package to the strategy's "
            f"`requirements.txt`.\n"
            f"3. If it's an Alpaca/auth error, confirm `ALPACA_API_KEY` and "
            f"`ALPACA_SECRET_KEY` are set on the runner.\n"
            f"4. If it's a data/shape error, check the data-loading section and "
            f"guard for empty responses.\n\n"
            f"_(Deterministic analysis — `claude` CLI was unavailable on the runner.)_\n")


def main(name: str) -> int:
    root = repo_root()
    rdir = results_dir(root, name)

    metrics = read_metrics(rdir) or {"status": "error", "error": "no metrics.json produced"}
    succeeded = metrics.get("status") == "ok"
    runlog_tail = _read(os.path.join(rdir, "run.log"), limit=6000)
    oracle_md = _read(os.path.join(root, "agents", "oracle.md"), limit=8000)

    summary = None
    if have_claude():
        log("invoking claude to analyze results")
        ok, text = run_claude(build_prompt(name, oracle_md, metrics, runlog_tail, succeeded))
        if ok:
            summary = text
            log("claude produced summary.md")
        else:
            log(f"claude unavailable/failed ({text[:120]}); using deterministic summary")
    else:
        log("claude CLI not found; using deterministic summary")

    if summary is None:
        summary = deterministic_summary(name, metrics, runlog_tail, succeeded)

    with open(os.path.join(rdir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary.rstrip() + "\n")
    log(f"wrote results/{name}/summary.md")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else strategy_name_from_branch()
    if not arg:
        print("usage: python agents/_runner/oracle.py <strategy-name>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(arg))
