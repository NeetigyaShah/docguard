# DocGuard — Architecture

Self-Healing Technical Documentation. Detects when code changes make Markdown
docs stale, verifies staleness, generates targeted corrections, gates on
confidence, and emits a GitHub PR (high confidence) or review comment (low).

## Pipeline

```
Code change (git diff)
  → [changes] diff parse + changed lines
  → [parsers] semantic code units (Python AST) touched by those lines
  → [changes] meaningful-change classification (down-rank noise)
  → [mapping] candidate doc sections (exact refs + lexical + embedding sim)
  → [staleness] LLM verification (structured verdict, per candidate)
  → [repair] targeted correction (only stale spans)
  → [repair] second-pass validation
  → [confidence] policy → AUTO_FIX | HUMAN_REVIEW | REPORT
  → [github] PR (high) or PR comment (medium/low) + loop prevention
  → PipelineResult (audit trail + dashboard payload)
```

## Modules (each owns a disjoint directory; all speak `models.py`)

| Module | Responsibility | Key output |
|---|---|---|
| `models.py` | Shared typed contract for every stage | pydantic models |
| `config.py` | Env/.env settings, safe offline defaults | `Settings` |
| `providers/` | Embedding + LLM abstraction; deterministic mocks; real OpenAI/Anthropic | `EmbeddingProvider`, `LLMProvider` |
| `parsers/` | Repo walker, Python AST parser, Markdown parser | `CodeUnit`, `DocSection` |
| `mapping/` | Code→doc linking + persistent vector index | `DocLink` |
| `changes/` | Git diff parse + meaningful-change classifier | `ChangeImpact` |
| `staleness/` | Staleness verifier (uses `LLMProvider`) | `StalenessVerdict` |
| `repair/` | Targeted repair + second-pass validator | `Repair`, `ValidationResult` |
| `confidence/` | Confidence → action policy | `ConfidenceLevel`, `Action` |
| `github/` | PR/comment integration, loop prevention | GitHub side effects |
| `pipeline.py` | Wires all stages end-to-end | `PipelineResult` |
| `cli.py` | `docguard` entrypoint (analyze/demo) | JSON / exit code |

## Design rules

- **Interface, never concrete.** The pipeline depends on `LLMProvider` /
  `EmbeddingProvider`, so mock ↔ real is a config swap.
- **Offline by default.** Mock providers make the entire system + test suite run
  with zero keys. Real providers are import-guarded extras.
- **Targeted edits.** Repairs are surgical token swaps on stale spans; unaffected
  text stays byte-identical. No whole-file rewrites.
- **Untrusted input.** Repo content (code, docs, PR text) is delimited as DATA in
  LLM prompts and never treated as instructions.
- **Cost control.** Candidate filtering + embedding cache + content hashing before
  any LLM call; only the minimal chunk is sent, never the repo.

## Persistence

- `.orchestrator/*.json` + `activity.jsonl` — authoritative build/run state
  (source of truth; survives `/clear` and new sessions).
- `.docguard_index/` — persistent embedding/mapping index (gitignored runtime).
- Dashboard reads `.orchestrator/` JSON; it visualizes, it does not own state.
