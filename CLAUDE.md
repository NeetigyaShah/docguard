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

## Real-LLM + real-world evaluation (session 2)
- Real LLM is wired via an **OpenAI-compatible endpoint** (`DOCGUARD_OPENAI_BASE_URL`).
  The key + config live in gitignored **`.env`** (survives `/clear`; never committed).
  Switch on with `DOCGUARD_LLM_PROVIDER=openai`. Tests stay `mock` by default.
- Evaluated on real Pydantic + FastAPI clones: evidence in `docs/eval/*.json` and
  README "Real-world evaluation". Reproduce: `python scripts/real_case_demo.py`,
  `python scripts/eval_realrepo.py --repo <path> --src <dir> --docs <dir>`.
- **Open follow-ups** (see `.orchestrator/state.json.open_followups`): (1) harden the
  real-LLM repair path (detects well, but returned no change on long prose), (2)
  improve code→doc mapping precision (word-match over-links).

## Rules that persist
- Offline mock providers are the default; real OpenAI/Anthropic/GitHub are opt-in
  behind interfaces. Never commit secrets.
- Never mark a milestone PASSED without executed test evidence in
  `.orchestrator/tests.json`.
- Repairs are targeted; unaffected doc text stays byte-identical.
- Update `.orchestrator/` + append `activity.jsonl` on every meaningful step.
