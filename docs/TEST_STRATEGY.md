# DocGuard — Test Strategy

Three levels, per the build brief:

1. **Feature tests** — written with each module (`tests/unit/`).
2. **Predefined milestone tests** — the scenarios named in the brief for each
   phase (`tests/integration/`, `tests/e2e/`).
3. **Orchestrator-added tests** — the orchestrator independently analyzes each
   finished phase and adds positive / negative / edge / failure / regression
   cases beyond the brief. Recorded in `.orchestrator/tests.json`.

## Determinism
All milestone + E2E tests run offline with the mock providers, so results are
reproducible and CI needs no secrets.

## Per-phase gate (serial)
After each phase: run predefined scenarios **one at a time**, record
`input / expected / actual / PASS|FAIL / evidence` into `.orchestrator/tests.json`
and `activity.jsonl`. Add orchestrator tests, run them serially, fix failures,
rerun the **whole** phase suite, then mark the milestone PASSED. A milestone is
never PASSED without executed evidence.

## Fixtures
`tests/fixtures/sample_project/` — a controlled repo with functions, a class +
methods, config keys, a CLI command, an endpoint, and Markdown docs. Change
scenarios (rename `role`→`user_role`, default `"viewer"`→`"member"`, removals,
plus negatives: whitespace/comment/internal-refactor) drive the whole pipeline
offline and produce the measured metrics.

## Quality gates (each milestone)
`pytest`, `ruff check`, `mypy` (best-effort), dashboard `tsc`+build, `docker build`.

## Evidence
Real command output is captured; nothing is marked PASSED on an agent's say-so.
