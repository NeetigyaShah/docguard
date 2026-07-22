# DocGuard — Implementation Plan

Priority order (from the build brief): **working E2E prototype → no lost work →
correctness → deterministic testing → transparency → persistence → modularity →
parallel speed → hardening → polish.**

## Phase 0 — Backbone (contracts) `[done]`
Shared `models.py`, `config.py`, provider abstraction + deterministic mocks,
real (import-guarded) providers. Everything downstream depends on this, so it is
built and committed to `integration` before any fan-out.

## Phase 1 — Code + Document Understanding
- Repo walker (glob src/docs, filter supported files).
- Python AST parser: functions/classes/methods, signatures, docstrings, config
  keys (module-level constants), CLI commands (argparse/click), endpoint
  decorators; stable semantic ids.
- Markdown parser: headings, nested heading paths, section content, line ranges,
  referenced symbols (backticks / code fences).
- Mapping: exact symbol refs + lexical overlap + embedding similarity
  (configurable threshold), persistent index.
- **Gate:** fixture repo → correct units, stable ids, nested sections, expected
  links, no spurious links. Serial milestone tests + orchestrator additions.

## Phase 2 — Change Detection
- Git diff parse (base/head), changed files + lines.
- Map changed lines → semantic units.
- Meaningful-change classifier: down-rank whitespace/comment/format/test/refactor;
  prioritize signature/param/default/API/config/CLI/capability changes.
- `ChangeImpact` per unit.
- **Gate:** scenarios A–G (whitespace, comment, rename, default, config, removed
  public, refactor) + orchestrator additions.

## Phase 3 — Staleness Detection
- Verifier feeds minimal context (old/new code, change kinds, doc section) to
  `LLMProvider`; structured `StalenessVerdict`.
- Anti-hallucination + prompt-injection delimiting.
- **Gate:** 5 labelled scenarios (STALE×3, ACCURATE, UNRELATED) + TP/FP/FN +
  orchestrator additions.

## Phase 4 — Repair + Validation + Confidence
- Targeted repair (preserve unaffected text/headings/formatting).
- Second-pass validator (factual / scope / style).
- Confidence policy: HIGH→auto-fix, MEDIUM→review, LOW→report; configurable.
- **Gate:** 7 scenarios incl. byte-identical preservation + orchestrator additions.

## Phase 5 — GitHub Action + PR/Comment
- `action.yml`, `Dockerfile`, example workflows.
- PyGithub integration: fix branch/PR (high), PR comment (medium/low),
  loop prevention (skip bot branches / `[docguard skip]`), least-privilege perms,
  graceful API errors, missing-credential handling.
- **Gate:** Docker build, action metadata, mocked GitHub API, comment/branch
  payloads, loop prevention, missing creds, API failure + orchestrator additions.
  Real GitHub E2E = external (gh available; opt-in).

## Phase 6 — E2E Demo + Dashboard + Metrics + README
- Deterministic offline demo (`create_user` rename+default + negatives).
- Metrics (TP/FP/FN/precision/recall/F1) from executed fixtures — never fabricated.
- React+Vite dashboard over `.orchestrator/` JSON.
- Polished README.
- **Gate:** 6 E2E scenarios (auto-fix, review, no-staleness, unrelated,
  multi-section, failure/recovery) + orchestrator additions.

## Parallelization
After Phase 0 contracts are committed, the leaf modules (parsers, changes,
staleness, repair, github, dashboard) touch disjoint directories and are fanned
out as parallel subagents. The orchestrator owns all integration, git, and
milestone verification. See `dependencies.json` for the DAG.
