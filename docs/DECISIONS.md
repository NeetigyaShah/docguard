# DocGuard — Decision Log

Records where the implementation deliberately diverges from the brief, with the
"why". The brief explicitly permits improving the structure and recording
decisions.

## D1 — Local file vector store as default, ChromaDB optional
The brief prefers ChromaDB but allows a clean local abstraction if Chroma adds
complexity. Default is a tiny file-backed vector store (numpy-free, stdlib
cosine) behind a `VectorStore` interface; Chroma is an optional backend. Keeps
the prototype dependency-light and fully offline. *Reversible: set
`DOCGUARD_VECTOR_BACKEND=chroma`.*

## D2 — Module-ownership isolation instead of N physical git worktrees for writes
The brief wants worktree isolation for parallel work. Every module owns a
**disjoint directory** and all cross-module contracts live in `models.py` (built
and committed first). With disjoint dirs there are no write conflicts, so
physical per-agent worktrees would add N repo copies + N merges for zero conflict
benefit. Parallel subagents therefore write into their owned directories and the
orchestrator performs all git commits/integration serially (matching "Main
Orchestrator controls integration" and "avoid multiple agents editing
high-conflict files"). Feature branches are still created per phase for history.
*Isolation guarantee preserved; ceremony removed.* — ponytail

## D3 — Deterministic mock LLM is a rule-based oracle, not a stub
The mock inspects the structured change context (renames/defaults/removals) and
doc text to return correct, reproducible verdicts and surgical repairs. This
makes the offline E2E demo produce **real** metrics rather than canned output,
and doubles as the reference behavior a real model should match.

## D4 — Repairs are surgical token swaps
Corrections use whole-word regex substitution on stale tokens only, so unaffected
text is byte-identical. Broad/removal-scope or high-risk changes are routed to
HUMAN_REVIEW rather than auto-edited, because deleting prose is riskier than
swapping a token.

## D5 — Python 3.13 used locally (brief asked 3.11+)
`requires-python = ">=3.11"`; the build machine has 3.13. No 3.13-only syntax used.
