# DocGuard — Resume Protocol (read this first)

**DocGuard = Self-Healing Technical Documentation.** Detects stale Markdown docs
from code changes, verifies staleness, generates targeted corrections, gates on
confidence, and emits a GitHub PR (high confidence) or review comment (low).

The **repository is the source of truth**, not any conversation. To resume:

1. Read this file.
2. Read `.orchestrator/state.json` — current phase, active milestone, next action.
3. Read `.orchestrator/features.json` — every feature + status + commit.
4. Read `.orchestrator/milestones.json` — phase gates + pass/fail.
5. Read `.orchestrator/blockers.json` — external blockers (API keys).
6. `git status` / `git branch` / `git log --oneline -15`.
7. Read `.orchestrator/tests.json` — recorded test evidence.
8. Continue from `state.json.next_action`.

## Layout
- `src/docguard/` — package (see `docs/ARCHITECTURE.md`).
- `tests/` — `unit/`, `integration/`, `e2e/`, `fixtures/`.
- `.orchestrator/` — authoritative build/run state + `activity.jsonl` audit log.
- `dashboard/` — React+Vite viewer over `.orchestrator/`.
- `docs/` — architecture, plan, infra, test strategy, decisions.

## Commands (Windows PowerShell; venv at `.venv`)
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"   # install
.\.venv\Scripts\python.exe -m pytest                    # all tests
.\.venv\Scripts\python.exe -m docguard demo             # offline E2E demo + metrics
.\.venv\Scripts\python.exe -m docguard analyze --base HEAD~1 --head HEAD   # analyze a diff
```
(POSIX: use `.venv/bin/python`.)

## Rules that persist
- Offline mock providers are the default; real OpenAI/Anthropic/GitHub are opt-in
  behind interfaces. Never commit secrets.
- Never mark a milestone PASSED without executed test evidence in
  `.orchestrator/tests.json`.
- Repairs are targeted; unaffected doc text stays byte-identical.
- Update `.orchestrator/` + append `activity.jsonl` on every meaningful step.
