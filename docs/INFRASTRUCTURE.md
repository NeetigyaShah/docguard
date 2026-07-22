# DocGuard — Infrastructure

Everything the prototype needs runs **locally and free**. External services are
optional and behind provider interfaces with deterministic fallbacks.

| Requirement | Purpose | Class | Mandatory? | Env vars | Fallback |
|---|---|---|---|---|---|
| Python 3.11+ | Core runtime | AVAILABLE_LOCAL | yes | — | — |
| pydantic / pydantic-settings | Models + config | FREE (pip) | yes | — | — |
| pytest / ruff / mypy | Tests + lint + types | FREE (pip) | dev | — | — |
| git CLI | Diff / branches | AVAILABLE_LOCAL | yes | — | — |
| Node 18+ / npm | Dashboard build | AVAILABLE_LOCAL | dashboard only | — | static JSON view |
| Docker | Package the Action | AVAILABLE_LOCAL | Action only | — | run CLI directly |
| OpenAI API | Real LLM + embeddings | OPTIONAL / paid | no | `OPENAI_API_KEY` | mock providers |
| Anthropic API | Real LLM | OPTIONAL / paid | no | `ANTHROPIC_API_KEY` | mock providers |
| GitHub token | Real PR/comment | FREE_TIER | Action only | `GITHUB_TOKEN` | dry-run payloads |
| ChromaDB | Vector store | OPTIONAL (pip) | no | — | local file vector store |

## Detected on this machine (build session)
- git ✅, python 3.13 ✅, node 22 ✅, npm ✅, docker ✅
- `gh` CLI ✅ authenticated (real GitHub E2E is possible, opt-in)
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GITHUB_TOKEN` **not set** →
  LLM + embeddings run through mocks by default.

## External blockers (tracked in `.orchestrator/blockers.json`)
- **Real LLM validation** — needs `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.
  Without it: staleness/repair use the deterministic mock (fully functional,
  not model-backed). Interface implemented; only live validation is blocked.
- **Real GitHub PR E2E** — needs `GITHUB_TOKEN` (or `gh` in CI). Integration +
  payloads tested against a mocked API locally.

## Secrets policy
Never hardcoded, never committed, never logged, never in PR comments / dashboard /
persisted state. Read from env / `.env` (gitignored). `.env.example` documents keys.
