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
thing). If the strategy succeeded, lead with a metrics table and a short
interpretation. If it failed, lead with the error, a root-cause analysis, and a
numbered list of concrete suggested fixes."""


def deterministic_summary(name, metrics, runlog_tail, succeeded) -> str:
    if succeeded:
        rows = [
            ("Trades", metrics.get("n_trades")),
            ("Win rate", f"{metrics.get('win_rate', 0) * 100:.1f}%"),
            ("Total P&L", f"${metrics.get('total_pnl', 0):,.2f}"),
            ("Avg / trade", f"${metrics.get('avg_pnl', 0):,.2f}"),
            ("Max drawdown", f"${metrics.get('max_drawdown', 0):,.2f}"),
            ("Sharpe", metrics.get("sharpe")),
            ("Best trade", f"${metrics.get('best_trade', 0):,.2f}"),
            ("Worst trade", f"${metrics.get('worst_trade', 0):,.2f}"),
            ("Data source", metrics.get("data_source")),
        ]
        table = "| Metric | Value |\n|---|---|\n" + "\n".join(
            f"| {k} | {v} |" for k, v in rows if v is not None
        )
        return (f"# Oracle Summary — {name}\n\n"
                f"**Result: SUCCESS**\n\n## Key metrics\n\n{table}\n\n"
                f"## Interpretation\n\n"
                f"The backtest completed and produced {metrics.get('n_trades', 0)} trades "
                f"with a {metrics.get('win_rate', 0) * 100:.1f}% win rate. "
                f"Review the equity curve (`equity_curve.png`) and `trades.csv` for detail. "
                f"_(Deterministic summary — `claude` CLI was unavailable on the runner.)_\n")
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
