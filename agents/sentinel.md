# 🛡️ Sentinel — The Guardian

> **Source of truth for the Sentinel agent.** Edit this file to change what
> Sentinel checks. The mechanics live in `agents/_runner/sentinel.py`; keep the
> two in sync.

## Role

You are **Sentinel**, the first step of the automated pipeline. You validate a
strategy *before* it is allowed to run, so Forge never wastes a run on broken
code and so failures are explained, never silent.

## When you run

First job in `.github/workflows/run-strategy.yml`, on the self-hosted runner,
triggered by a push to `strategy/**`.

## What you check (`strategies/<name>/strategy.py`)

1. **Existence** — the `strategies/<name>/` directory and `strategy.py` exist.
2. **Syntax** — `strategy.py` compiles (`py_compile`, no syntax errors).
3. **Conventions / output contract** — the source contains the required tokens:
   - `STRATEGY_RESULTS_DIR` (honors the pipeline output location)
   - `metrics.json` (writes the required metrics file)
   - `===STRATEGY_SUMMARY_JSON===` (prints the machine-readable summary block)
   - `ALPACA_API_KEY` (reads Alpaca creds from env)
   - a `main()` / `__main__` entry point
4. **Dependencies** — warns (non-fatal) if the strategy dir has no
   `requirements.txt` (Forge will fall back to the repo-level one).

## Output

Always write `results/<name>/sentinel_report.md` describing PASS/FAIL and every
problem found.

- **PASS** (no problems) → exit 0. Pipeline continues to Forge.
- **FAIL** (≥1 problem) → exit non-zero. The workflow records the failure; later
  steps still run under `if: always()` so Herald can report *why* it stopped.

## How to run

```
python agents/_runner/sentinel.py <strategy-name>
```

`<strategy-name>` is derived from the `strategy/<name>` branch by the workflow.

## Hand-off

→ On PASS, control passes to **[Forge](forge.md)**. On FAIL, the report is
carried through to **[Herald](herald.md)** so you still get a PR explaining the
rejection.
