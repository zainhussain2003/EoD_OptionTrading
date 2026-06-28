#!/usr/bin/env python
"""
Shared helpers for the pipeline runner scripts (Sentinel/Forge/Oracle/Herald).

Keep this small and dependency-free (stdlib only) so it always imports, even
before a strategy's requirements are installed.
"""
from __future__ import annotations

import os
import re
import sys
import json
import subprocess
from datetime import datetime, timezone


def repo_root() -> str:
    """Repo root = two levels up from this file (agents/_runner/ -> repo)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def strategy_name_from_branch() -> str:
    """Derive <name> from a 'strategy/<name>' branch. Falls back to git."""
    ref = os.environ.get("GITHUB_REF_NAME") or os.environ.get("STRATEGY_NAME") or ""
    if ref.startswith("strategy/"):
        ref = ref[len("strategy/"):]
    if not ref:
        try:
            ref = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
            ).strip()
            if ref.startswith("strategy/"):
                ref = ref[len("strategy/"):]
        except Exception:
            ref = ""
    return ref


def strategy_dir(root: str, name: str) -> str:
    return os.path.join(root, "strategies", name)


def results_dir(root: str, name: str) -> str:
    d = os.path.join(root, "results", name)
    os.makedirs(d, exist_ok=True)
    return d


def log(msg: str) -> None:
    print(f"  [{_caller()}] {msg}", flush=True)


def _caller() -> str:
    # best-effort: name of the top script (sentinel/forge/oracle/herald)
    base = os.path.basename(sys.argv[0]) if sys.argv else ""
    return os.path.splitext(base)[0] or "pipeline"


def write_report(rdir: str, filename: str, title: str, body_lines) -> str:
    os.makedirs(rdir, exist_ok=True)
    path = os.path.join(rdir, filename)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {title}", "", f"_Generated {ts}_", ""]
    lines.extend(body_lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def read_metrics(rdir: str) -> dict | None:
    path = os.path.join(rdir, "metrics.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_summary_block(text: str) -> dict | None:
    """Extract the JSON between ===STRATEGY_SUMMARY_JSON=== markers."""
    m = re.search(r"===STRATEGY_SUMMARY_JSON===\s*(\{.*?\})\s*===END_SUMMARY===",
                  text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def have_claude() -> bool:
    """Is the `claude` CLI available on PATH?"""
    from shutil import which
    return which("claude") is not None


def run_claude(prompt: str, timeout: int = 600) -> tuple[bool, str]:
    """Call `claude -p` headless using the runner's local login. Returns
    (ok, text). Never raises — callers fall back to deterministic output."""
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return True, proc.stdout.strip()
        return False, (proc.stderr or proc.stdout or "claude returned no output").strip()
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
