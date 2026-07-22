"""Phase 1 milestone scenarios (predefined from the brief + orchestrator-added)."""

from __future__ import annotations

from pathlib import Path

from tests.milestones import Scenario

from docguard.mapping.mapper import build_links, sections_for_unit
from docguard.models import MapMethod
from docguard.parsers.code_python import parse_python_file, parse_python_source
from docguard.parsers.docs_markdown import parse_markdown_file, parse_markdown_source
from docguard.parsers.repo_walker import find_code, find_docs
from docguard.providers.mock import MockEmbeddingProvider

ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"

_UNITS = [u for f in find_code(ROOT, ["src"]) for u in parse_python_file(f, ROOT)]
_SECS = [s for f in find_docs(ROOT, ["docs"]) for s in parse_markdown_file(f, ROOT)]
_LINKS = build_links(_UNITS, _SECS, MockEmbeddingProvider(), threshold=0.35)
_Q = {u.qualified_name: u for u in _UNITS}
_SID = {tuple(s.heading_path): s.id for s in _SECS}

SCENARIOS = [
    # ---- predefined (brief §19) ----
    Scenario("P1-01", 1, "Correct semantic chunks extracted (all kinds present)",
             "parse sample_project/src",
             True,
             lambda: {"function", "class", "method", "config_key", "cli_command", "endpoint"}
             <= {u.kind.value for u in _UNITS}),
    Scenario("P1-02", 1, "Stable ids generated (re-parse identical)",
             "parse users.py twice",
             True,
             lambda: [u.id for u in parse_python_source(Path(ROOT / "src/users.py").read_text(), "src/users.py")]
             == [u.id for u in parse_python_source(Path(ROOT / "src/users.py").read_text(), "src/users.py")]),
    Scenario("P1-03", 1, "Headings parsed", "parse docs/api.md",
             True, lambda: any(s.heading == "create_user" for s in _SECS)),
    Scenario("P1-04", 1, "Nested heading path parsed (depth 3)",
             "create_user section", ["API Reference", "Users", "create_user"],
             lambda: next(s.heading_path for s in _SECS if s.heading == "create_user")),
    Scenario("P1-05", 1, "References extracted from section", "create_user section refs",
             True, lambda: {"create_user", "role", "viewer"}
             <= set(next(s.referenced_symbols for s in _SECS if s.heading == "create_user"))),
    Scenario("P1-06", 1, "Expected code->doc link created", "create_user unit",
             True, lambda: _SID[("API Reference", "Users", "create_user")]
             in set(sections_for_unit(_Q["create_user"].id, _LINKS))),
    Scenario("P1-07", 1, "Unrelated sections NOT linked", "create_user unit vs Timeout",
             False, lambda: _SID[("Configuration", "Timeout")]
             in set(sections_for_unit(_Q["create_user"].id, _LINKS))),

    # ---- orchestrator-added ----
    Scenario("P1-08", 1, "[edge] empty source yields no units", "parse ''",
             [], lambda: parse_python_source("", "empty.py"), kind="orchestrator"),
    Scenario("P1-09", 1, "[negative] syntactically broken python does not crash",
             "parse 'def (: bad'", [],
             lambda: parse_python_source("def (: bad", "bad.py"), kind="orchestrator"),
    Scenario("P1-10", 1, "[edge] heading inside fenced code block is not a section",
             "```\\n# not a heading\\n```", 0,
             lambda: len(parse_markdown_source("```\n# not a heading\n```\n", "x.md")),
             kind="orchestrator"),
    Scenario("P1-11", 1, "[regression] all unit ids unique (no method/function id collision)",
             "all fixture units", True,
             lambda: len({u.id for u in _UNITS}) == len(_UNITS), kind="orchestrator"),
    Scenario("P1-12", 1, "[edge] prose section with no refs links to nothing",
             "API Reference root section", False,
             lambda: any(link.doc_section_id == _SID[("API Reference",)] for link in _LINKS),
             kind="orchestrator"),
    Scenario("P1-13", 1, "[regression] config key maps via EXACT method",
             "MAX_RETRIES", True,
             lambda: any(link.code_unit_id == _Q["MAX_RETRIES"].id and link.method == MapMethod.EXACT
                         for link in _LINKS), kind="orchestrator"),
    Scenario("P1-14", 1, "[edge] endpoint symbols include handler function name",
             "GET /users unit", True,
             lambda: "list_users" in _Q["GET /users"].symbols, kind="orchestrator"),
]
