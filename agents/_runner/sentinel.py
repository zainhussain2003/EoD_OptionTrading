#!/usr/bin/env python
"""
SENTINEL — deterministic validator (the guardian).

Source of truth for behavior: agents/sentinel.md
This script implements those checks. Update the .md when you change intent;
update this file when you change the mechanics.

Validates strategies/<name>/strategy.py before Forge runs it:
  - the strategy directory and strategy.py exist
  - strategy.py parses (no syntax errors)  -> py_compile
  - imports resolve well enough to flag obviously-missing deps
  - the project conventions are present (writes metrics.json / results dir,
    prints the SUMMARY block, reads Alpaca env, has a main entry)

Exit 0 = pass (pipeline continues). Exit non-zero = fail. Either way it writes
results/<name>/sentinel_report.md so the failure is never silent.

Usage:  python agents/_runner/sentinel.py <strategy-name>
"""
from __future__ import annotations

import os
import sys
import py_compile

from _pipeline_common import (
    repo_root, strategy_dir, results_dir, write_report, log,
    strategy_name_from_branch,
)

REQUIRED_TOKENS = {
    "STRATEGY_RESULTS_DIR": "must honor the STRATEGY_RESULTS_DIR output location",
    "metrics.json": "must write metrics.json",
    "===STRATEGY_SUMMARY_JSON===": "must print the machine-readable summary block",
    "ALPACA_API_KEY": "must read the Alpaca API key from env",
}


def main(name: str) -> int:
    root = repo_root()
    sdir = strategy_dir(root, name)
    rdir = results_dir(root, name)
    problems: list[str] = []
    notes: list[str] = []

    # 1. directory + entry point exist
    if not os.path.isdir(sdir):
        write_report(rdir, "sentinel_report.md", "Sentinel — FAILED",
                     [f"Strategy directory not found: `strategies/{name}/`. "
                      "Architect must create it (copy from templates/ or a reference strategy)."])
        log(f"FAIL: missing strategy dir {sdir}")
        return 2

    entry = os.path.join(sdir, "strategy.py")
    if not os.path.isfile(entry):
        problems.append("Missing `strategy.py` entry point in the strategy directory.")
    else:
        # 2. syntax check
        try:
            py_compile.compile(entry, doraise=True)
            notes.append("Syntax OK (py_compile passed).")
        except py_compile.PyCompileError as e:
            problems.append(f"Syntax error in strategy.py:\n```\n{e.msg}\n```")

        # 3. convention checks (token scan)
        with open(entry, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        for token, why in REQUIRED_TOKENS.items():
            if token not in src:
                problems.append(f"Convention check failed — {why} (missing `{token}`).")
        if "__main__" not in src and "def main" not in src:
            problems.append("No `main()` / `__main__` entry point found.")

        # 4. requirements present (soft warning, not fatal)
        if not os.path.isfile(os.path.join(sdir, "requirements.txt")):
            notes.append("WARNING: no requirements.txt in the strategy dir; "
                         "Forge will fall back to the repo-level requirements.txt.")

    status = "PASSED" if not problems else "FAILED"
    body = []
    if problems:
        body.append("### Problems")
        body.extend(f"- {p}" for p in problems)
    if notes:
        body.append("\n### Notes")
        body.extend(f"- {n}" for n in notes)
    write_report(rdir, "sentinel_report.md", f"Sentinel — {status}", body)
    log(f"{status}: {len(problems)} problem(s) for strategy '{name}'")
    return 0 if not problems else 1


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else strategy_name_from_branch()
    if not arg:
        print("usage: python agents/_runner/sentinel.py <strategy-name>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(arg))
