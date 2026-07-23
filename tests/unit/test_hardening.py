# Neetigya, 2026-07-22: new file — tests for the mapping-precision + real-LLM repair fixes.
"""Session-3 hardening: mapping precision + real-LLM repair contract.

Both are offline/deterministic — the real repair path is exercised through a
stub `_complete` so no API key is needed.
"""

from docguard.mapping.mapper import _exact, build_links, sections_for_unit
from docguard.models import (
    ChangeImpact,
    ChangeKind,
    CodeUnit,
    CodeUnitKind,
    DocSection,
    MapMethod,
    RiskLevel,
    StalenessLabel,
    StalenessVerdict,
)
from docguard.providers.mock import MockEmbeddingProvider
from docguard.providers.real import _JsonLLM, _repair_prompt


def _unit(name: str) -> CodeUnit:
    return CodeUnit(
        id=f"m.py::{name}::function",
        kind=CodeUnitKind.FUNCTION,
        name=name,
        qualified_name=f"m.{name}",
        signature=f"def {name}(x, y): ...",
        file="m.py",
        start_line=1,
        end_line=2,
        symbols=[name],
    )


def _section(heading, content) -> DocSection:
    from docguard.parsers.docs_markdown import _symbols

    return DocSection(
        id=DocSection.make_id("d.md", [heading]),
        doc_path="d.md",
        heading=heading,
        heading_path=[heading],
        content=content,
        referenced_symbols=_symbols(heading + "\n" + content),
    )


# --------------------------------------------------------------------------- #
# Mapping precision
# --------------------------------------------------------------------------- #
def test_focused_section_is_documentation():
    # symbol in heading, or short blurb about it -> documents it (EXACT).
    assert _exact(_unit("Widget"), _section("Widget", "`Widget` draws a box."))
    assert _exact(_unit("MAX_TRIES"), _section("Retries", "`MAX_TRIES` sets the retry count. Default 3."))


def test_lone_mention_in_long_tutorial_is_not_documentation():
    # `Widget` name-dropped once inside a long section about something else must
    # NOT count as documentation (this was the over-linking bug).
    prose = (
        "This guide builds a settings screen. You add a form, then a save button. "
        "The layout uses a grid. You can drop a `Widget` anywhere in the tree if you "
        "want, but that is optional. Most screens use panels and rows instead. "
        "Finish by wiring the submit handler and validating the inputs on change."
    )
    section = _section("Building a settings screen", prose)
    assert len(section.content) > 240  # genuinely a long section
    assert not _exact(_unit("Widget"), section)


def test_build_links_drops_tutorial_overlink():
    unit = _unit("Widget")
    focused = _section("Widget", "`Widget` draws a box.")
    tutorial = _section(
        "Guide",
        "A long walkthrough. " * 20 + "It briefly uses `Widget` once. " + "More prose. " * 20,
    )
    links = build_links([unit], [focused, tutorial], MockEmbeddingProvider(), threshold=0.35)
    linked = set(sections_for_unit(unit.id, links))
    assert focused.id in linked
    exact_to_tutorial = [
        link for link in links
        if link.doc_section_id == tutorial.id and link.method == MapMethod.EXACT
    ]
    assert not exact_to_tutorial  # no perfect-score link off a lone mention


# --------------------------------------------------------------------------- #
# Real-LLM repair contract
# --------------------------------------------------------------------------- #
_IMPACT = ChangeImpact(
    file="m.py",
    unit_name="greet",
    old_source="def greet(name): ...",
    new_source="def greet(username): ...",
    change_kinds=[ChangeKind.PARAM_RENAMED],
    meaningful=True,
)
_UNIT = _unit("greet")
_SECTION = _section("greet", "Call `greet` with `name` to say hello.")
_VERDICT = StalenessVerdict(
    doc_section_id=_SECTION.id,
    code_unit_id=_UNIT.id,
    label=StalenessLabel.STALE,
    confidence=0.9,
    reason="`name` was renamed to `username`.",
    stale_claims=["name"],
    correction_scope="Rename `name` -> `username`.",
    risk=RiskLevel.LOW,
)


class _StubLLM(_JsonLLM):
    """Returns a canned completion so the parse/diff contract runs without a key."""

    name = "stub"

    def __init__(self, response: str) -> None:
        super().__init__()
        self.response = response
        self.last_prompt = ""

    def _complete(self, system: str, user: str) -> str:
        self.last_prompt = user
        return self.response


def test_repair_prompt_includes_new_code():
    # Root cause of "no change": the model never saw the new code. It must now.
    prompt = _repair_prompt(_VERDICT, _IMPACT, _UNIT, _SECTION)
    assert "def greet(username)" in prompt
    assert "username" in prompt


def test_repair_applies_change_and_fills_diff():
    fixed = "Call `greet` with `username` to say hello."
    llm = _StubLLM(f'{{"repaired": "{fixed}", "changed": true}}')
    repair = llm.repair_section(verdict=_VERDICT, impact=_IMPACT, code_unit=_UNIT, section=_SECTION)
    assert repair.changed
    assert repair.repaired_content == fixed
    assert repair.unified_diff  # non-empty when something changed
    assert "def greet(username)" in llm.last_prompt


def test_repair_salvages_malformed_json():
    # weak models emit unescaped newlines inside the string -> json.loads fails.
    fixed = "line one\nfixed `username` line"
    llm = _StubLLM('{"repaired": "line one\nfixed `username` line", "changed": true}')
    repair = llm.repair_section(verdict=_VERDICT, impact=_IMPACT, code_unit=_UNIT, section=_SECTION)
    assert repair.changed
    assert "username" in repair.repaired_content
    assert repair.repaired_content == fixed


def test_repair_no_change_when_model_echoes():
    llm = _StubLLM(f'{{"repaired": "{_SECTION.content}", "changed": false}}')
    repair = llm.repair_section(verdict=_VERDICT, impact=_IMPACT, code_unit=_UNIT, section=_SECTION)
    assert not repair.changed
    assert repair.unified_diff == ""
