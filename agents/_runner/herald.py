#!/usr/bin/env python
"""
HERALD — the messenger.

Source of truth for behavior: agents/herald.md

Final pipeline step. It:
  1. Commits everything under results/<name>/ back to the strategy branch and pushes.
  2. Opens a PR from strategy/<name> -> main (or reuses the existing one), putting
     Oracle's summary in the PR body.
  3. Posts a concise key-metrics comment on the PR so it's readable from a phone.
  4. On strategy failure, the PR/comment carry the error analysis and fixes.

Git/gh operations are deterministic (we never let an LLM run git blindly in CI).
The short PR comment headline can optionally be polished by the local `claude`
CLI; if unavailable it uses a deterministic headline.

Requires `gh` authenticated on the runner (it is, for zainhussain2003).

Usage:  python agents/_runner/herald.py <strategy-name>
"""
from __future__ import annotations

import os
import sys
import json
import subprocess

from _pipeline_common import (
    repo_root, results_dir, read_metrics, have_claude, run_claude, log,
    strategy_name_from_branch,
)

BRANCH_PREFIX = "strategy/"
BASE_BRANCH = "main"


def sh(args, cwd=None, check=False) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{out}")
    return proc.returncode, out.strip()


def current_branch(root) -> str:
    ref = os.environ.get("GITHUB_REF_NAME")
    if ref:
        return ref
    _, out = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    return out


def commit_and_push(root, name, branch) -> None:
    # Identity (safe defaults for CI; harmless locally).
    sh(["git", "config", "user.name", "eod-pipeline-bot"], cwd=root)
    sh(["git", "config", "user.email", "eod-pipeline-bot@users.noreply.github.com"], cwd=root)
    sh(["git", "add", f"results/{name}"], cwd=root)
    rc, _ = sh(["git", "diff", "--cached", "--quiet"], cwd=root)
    if rc == 0:
        log("no result changes to commit")
    else:
        sh(["git", "commit", "-m", f"results: {name} pipeline run [skip ci]"], cwd=root)
        log("committed results")
    rc, out = sh(["git", "push", "origin", f"HEAD:{branch}"], cwd=root)
    log("pushed results" if rc == 0 else f"push note: {out.splitlines()[-1] if out else 'n/a'}")


def metrics_comment(name, metrics, succeeded) -> str:
    if succeeded:
        headline = (f"`{name}` ran OK — "
                    f"{metrics.get('n_trades', 0)} trades, "
                    f"win rate {metrics.get('win_rate', 0) * 100:.1f}%, "
                    f"P&L ${metrics.get('total_pnl', 0):,.2f}")
        if have_claude():
            ok, text = run_claude(
                "In ONE short line (<140 chars, no markdown headers), summarize this "
                f"option-strategy backtest result for a phone notification: {json.dumps(metrics)}"
            )
            if ok and text:
                headline = text.splitlines()[0][:200]
        body = (f"### 📈 {name} — results\n\n"
                f"{headline}\n\n"
                f"| Metric | Value |\n|---|---|\n"
                f"| Trades | {metrics.get('n_trades', 0)} |\n"
                f"| Win rate | {metrics.get('win_rate', 0) * 100:.1f}% |\n"
                f"| Total P&L | ${metrics.get('total_pnl', 0):,.2f} |\n"
                f"| Max drawdown | ${metrics.get('max_drawdown', 0):,.2f} |\n"
                f"| Sharpe | {metrics.get('sharpe', 0)} |\n"
                f"| Data source | {metrics.get('data_source', 'n/a')} |\n\n"
                f"Full analysis: `results/{name}/summary.md` · "
                f"chart: `results/{name}/equity_curve.png`")
    else:
        body = (f"### ❌ {name} — FAILED\n\n"
                f"```\n{metrics.get('error', 'unknown error')}\n```\n\n"
                f"See `results/{name}/summary.md` for root-cause analysis and "
                f"suggested fixes.")
    return body


def ensure_pr(root, name, branch, summary_body) -> str:
    """Create the PR if missing; return its number/url. Reuse if it exists."""
    rc, out = sh(["gh", "pr", "view", branch, "--json", "number,url",
                  "-q", ".number"], cwd=root)
    if rc == 0 and out.strip().isdigit():
        log(f"PR already exists (#{out.strip()})")
        return out.strip()
    title = f"Strategy: {name}"
    rc, out = sh(["gh", "pr", "create", "--base", BASE_BRANCH, "--head", branch,
                  "--title", title, "--body", summary_body], cwd=root)
    log("opened PR" if rc == 0 else f"PR create note: {out.splitlines()[-1] if out else 'n/a'}")
    # fetch number again
    rc, num = sh(["gh", "pr", "view", branch, "--json", "number", "-q", ".number"], cwd=root)
    return num.strip() if rc == 0 else ""


def main(name: str) -> int:
    root = repo_root()
    rdir = results_dir(root, name)
    branch = current_branch(root)
    if not branch.startswith(BRANCH_PREFIX):
        log(f"WARNING: branch '{branch}' is not a strategy/* branch; proceeding anyway")

    metrics = read_metrics(rdir) or {"status": "error", "error": "no metrics.json produced"}
    succeeded = metrics.get("status") == "ok"

    summary_path = os.path.join(rdir, "summary.md")
    summary_body = ""
    if os.path.isfile(summary_path):
        with open(summary_path, "r", encoding="utf-8", errors="replace") as f:
            summary_body = f.read()
    if not summary_body:
        summary_body = f"# {name}\n\n(No Oracle summary was produced.)"

    # 1. commit + push results
    commit_and_push(root, name, branch)

    # 2. ensure PR exists with summary in the body
    pr = ensure_pr(root, name, branch, summary_body)

    # 3. post metrics comment
    if pr:
        comment = metrics_comment(name, metrics, succeeded)
        rc, out = sh(["gh", "pr", "comment", pr, "--body", comment], cwd=root)
        log("posted metrics comment" if rc == 0 else f"comment note: {out[:120]}")
    else:
        log("no PR number resolved; skipped comment")

    log(f"done — strategy {'SUCCEEDED' if succeeded else 'FAILED'}")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else strategy_name_from_branch()
    if not arg:
        print("usage: python agents/_runner/herald.py <strategy-name>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(arg))
