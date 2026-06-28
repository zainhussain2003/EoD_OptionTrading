# CLAUDE.md — EoD Option Trading Pipeline

Automated multi-agent pipeline for end-of-day (EoD) option-trading research. You
describe a strategy idea (from Claude Code on your phone); a team of five
"superhero" agents designs it, runs it on the laptop, analyzes the results, and
delivers them back as a PR you can read on your phone.

## The five agents

Each agent has its own instruction file in `agents/`. **Each `.md` file is that
agent's source of truth — to change an agent's behavior, edit its `.md` file.**
The deterministic agents (Sentinel, Forge) have a matching script in
`agents/_runner/`; keep the `.md` and the script in sync. The reasoning agents
(Oracle, Herald) feed their `.md` to the local `claude` CLI at run time.

| Agent | File | Runs | Does |
|-------|------|------|------|
| 🦸 **Architect** | [`agents/architect.md`](agents/architect.md) | Interactively (your phone) | Turns your idea into code: branch, strategy dir, modified code, commit, push. |
| 🛡️ **Sentinel** | [`agents/sentinel.md`](agents/sentinel.md) | CI step 1 | Validates the strategy (syntax, imports, conventions) before it runs. |
| 🔨 **Forge** | [`agents/forge.md`](agents/forge.md) | CI step 2 (self-hosted) | Installs deps, runs the strategy on the laptop, captures all output. |
| 🔮 **Oracle** | [`agents/oracle.md`](agents/oracle.md) | CI step 3 | Analyzes results or errors; writes `summary.md`. |
| 📣 **Herald** | [`agents/herald.md`](agents/herald.md) | CI step 4 | Commits results, opens the PR, posts a metrics comment. |

## Pipeline flow

```
You (phone) ──idea──▶ Architect ──push strategy/<name>──▶ GitHub Actions
                                                              │
   Sentinel ─pass▶ Forge ─output▶ Oracle ─summary▶ Herald ──▶ PR ──▶ You (phone)
      │ fail ───────────────────────────────────────────────▶ PR (explains why)
```

Architect runs interactively and ends by pushing a `strategy/<name>` branch. That
push triggers [`.github/workflows/run-strategy.yml`](.github/workflows/run-strategy.yml),
which runs Sentinel → Forge → Oracle → Herald on the **self-hosted Windows
runner**. Oracle and Herald run with `if: always()`, so even a Sentinel rejection
or a strategy crash still produces a PR explaining what happened — **failures are
reported, never silent.**

## Execution model (hybrid)

- **Sentinel & Forge** are deterministic Python (`agents/_runner/*.py`) — fast,
  free, reproducible.
- **Oracle & Herald** call the local `claude` CLI (your Claude subscription login
  on the runner) for the narrative/PR text, each with a deterministic fallback so
  the pipeline never goes silent if `claude` is unavailable.

## Directory layout

| Path | Purpose |
|------|---------|
| `agents/` | The five agent instruction files + `_runner/` scripts. |
| `templates/eod_strategy_template/` | Reference strategy structure (put-selling example). |
| `strategies/<name>/` | One self-contained directory per automated strategy. |
| `results/<name>/` | Pipeline output per strategy (committed by Herald). |
| `.github/workflows/` | `run-strategy.yml` (pipeline) + `runner-smoke-test.yml`. |
| `calls/`, `puts/`, `thursday-friday/` | **Legacy reference strategies** — pre-existing, untouched. Architect may copy from these. |

## Strategy directory convention

When Architect creates a new strategy:
1. Create a new directory `strategies/<name>/`.
2. Copy the code structure from the **most relevant existing strategy** in
   `strategies/` (or the legacy `calls/`/`puts/`/`thursday-friday/`).
3. If none fits, copy from `templates/eod_strategy_template/`.
4. Modify the copied code (mainly `config.py` and `strategy.py` Section 3) to
   implement the new idea. Keep the directory self-contained.

## The output contract

Every `strategies/<name>/strategy.py` must:
- Read `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` from env.
- Write to `STRATEGY_RESULTS_DIR` (set by the pipeline; defaults to `./output`):
  `metrics.json` (**required**), `trades.csv`, `equity_curve.png`.
- Print the `===STRATEGY_SUMMARY_JSON=== … ===END_SUMMARY===` block.
- Exit 0 on success; write `metrics.json` with `status:"error"` and exit non-zero
  on failure.

Sentinel enforces this; Forge, Oracle, and Herald consume it.

## Naming & conventions

- **Branch:** `strategy/<name>`  ·  **Strategy dir:** `strategies/<name>/`  ·
  **Results dir:** `results/<name>/`. The `<name>` is identical across all three.
- **CRITICAL:** Always use `strategy/<name>` as the branch name. Do **NOT** use the
  default `claude/` prefix. The entire pipeline depends on this naming convention —
  the `run-strategy.yml` workflow only triggers on `strategy/**` branches, so a
  `claude/` branch silently runs nothing.
- **`<name>`** is lowercase, hyphen-separated, descriptive
  (e.g. `spy-weekly-5delta-puts`).
- **Python:** use `python` (not `python3`) — this repo targets **Windows**.
  Developed against **Python 3.13+** (the laptop currently runs 3.14).
- **Data:** Alpaca **paper** + market-data API, read-only (no orders). Keys via
  env `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`; never commit a real `.env`.

## Setup

- Pipeline runs on a self-hosted GitHub Actions runner on the laptop — see
  [`RUNNER_SETUP.md`](RUNNER_SETUP.md).
- Required GitHub secrets: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.
- The runner must be logged into the `claude` CLI (your subscription) and have
  `gh` authenticated.
