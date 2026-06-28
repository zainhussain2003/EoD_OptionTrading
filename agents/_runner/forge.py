#!/usr/bin/env python
"""
FORGE — deterministic execution engine.

Source of truth for behavior: agents/forge.md

Runs on the self-hosted Windows runner. It:
  1. Installs the strategy's dependencies (strategy requirements.txt, else repo).
  2. Executes strategies/<name>/strategy.py with STRATEGY_RESULTS_DIR pointed at
     results/<name>/, capturing stdout + stderr.
  3. Saves the raw output to results/<name>/run.log.
  4. If the script crashes, captures the full traceback and writes a structured
     results/<name>/metrics.json with status=error (if the script didn't already).
  5. Writes results/<name>/forge_status.json so downstream steps know what happened.

Forge ALWAYS exits 0 so Oracle and Herald still run (the workflow uses
`if: always()` too, as belt-and-suspenders). Success/failure of the *strategy*
is recorded in forge_status.json, not in Forge's own exit code.

Usage:  python agents/_runner/forge.py <strategy-name>
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
from datetime import datetime, timezone

from _pipeline_common import (
    repo_root, strategy_dir, results_dir, read_metrics, parse_summary_block, log,
    strategy_name_from_branch,
)


def pip_install(req_path: str) -> str:
    log(f"installing deps from {os.path.relpath(req_path)}")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_path, "--quiet",
         "--disable-pip-version-check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        log(f"WARNING: pip install returned {proc.returncode}; continuing")
    return out


def main(name: str) -> int:
    root = repo_root()
    sdir = strategy_dir(root, name)
    rdir = results_dir(root, name)
    entry = os.path.join(sdir, "strategy.py")

    status = {"strategy": name, "started_at": datetime.now(timezone.utc).isoformat()}

    if not os.path.isfile(entry):
        status.update(strategy_ok=False, reason="strategy.py not found", returncode=None)
        _write_status(rdir, status)
        log(f"strategy.py missing for '{name}' — nothing to run")
        return 0

    # 1. dependencies
    pip_log = ""
    req = os.path.join(sdir, "requirements.txt")
    if not os.path.isfile(req):
        req = os.path.join(root, "requirements.txt")
    if os.path.isfile(req):
        pip_log = pip_install(req)

    # 2. run the strategy
    env = dict(os.environ)
    env["STRATEGY_RESULTS_DIR"] = rdir
    env["PYTHONIOENCODING"] = "utf-8"      # keep box-drawing / em-dash output sane
    env.setdefault("PYTHONUNBUFFERED", "1")

    log(f"running {os.path.relpath(entry)} (cwd={os.path.relpath(sdir)})")
    proc = subprocess.run(
        [sys.executable, "strategy.py"],
        cwd=sdir, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    stdout, stderr, rc = proc.stdout or "", proc.stderr or "", proc.returncode

    # 3. save raw output
    runlog = os.path.join(rdir, "run.log")
    with open(runlog, "w", encoding="utf-8") as f:
        f.write(f"=== pip install ===\n{pip_log}\n")
        f.write(f"=== strategy stdout (exit {rc}) ===\n{stdout}\n")
        f.write(f"=== strategy stderr ===\n{stderr}\n")
    log(f"captured output -> {os.path.relpath(runlog)} (exit {rc})")

    # 4. ensure metrics.json exists (recover from stdout block or synthesize error)
    metrics = read_metrics(rdir)
    if metrics is None:
        metrics = parse_summary_block(stdout)
        if metrics is not None:
            with open(os.path.join(rdir, "metrics.json"), "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2)
            log("recovered metrics.json from stdout summary block")
    if metrics is None:
        # No structured output at all -> record the crash.
        tail = "\n".join(stderr.strip().splitlines()[-30:]) or "no stderr captured"
        metrics = {"status": "error",
                   "error": tail.splitlines()[-1] if tail else "unknown error",
                   "traceback": tail}
        with open(os.path.join(rdir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        log("no metrics produced; wrote error metrics.json")

    strategy_ok = (rc == 0) and (metrics.get("status") != "error")
    status.update(
        strategy_ok=strategy_ok,
        returncode=rc,
        metrics_status=metrics.get("status"),
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_status(rdir, status)
    log(f"strategy_ok={strategy_ok}")
    return 0  # Forge never fails the pipeline itself


def _write_status(rdir: str, status: dict) -> None:
    with open(os.path.join(rdir, "forge_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else strategy_name_from_branch()
    if not arg:
        print("usage: python agents/_runner/forge.py <strategy-name>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(arg))
