"""Phase 4 milestone scenarios (7 predefined + orchestrator-added)."""

from __future__ import annotations

from pathlib import Path

from tests.milestones import Scenario

from docguard.changes.classify import classify_change
from docguard.confidence.policy import decide
from docguard.config import load_settings
from docguard.parsers.code_python import parse_python_file, parse_python_source
from docguard.parsers.docs_markdown import parse_markdown_file
from docguard.parsers.repo_walker import find_code, find_docs
from docguard.providers.mock import MockLLMProvider
from docguard.repair.repair import repair_section
from docguard.repair.validate import validate_repair
from docguard.staleness.verifier import verify_section

ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"
_UNITS = [u for f in find_code(ROOT, ["src"]) for u in parse_python_file(f, ROOT)]
_SECS = [s for f in find_docs(ROOT, ["docs"]) for s in parse_markdown_file(f, ROOT)]
_Q = {u.qualified_name: u for u in _UNITS}
_SEC = {tuple(s.heading_path): s for s in _SECS}
_LLM = MockLLMProvider()
_CFG = load_settings()

_CU = _Q["create_user"]
_CU_SEC = _SEC[("API Reference", "Users", "create_user")]
_RM = _Q["UserService.remove_member"]
_RM_SEC = _SEC[("API Reference", "Users", "UserService.remove_member")]


def _impact(unit, transform):
    return classify_change(unit, parse_python_source(transform(unit.source), unit.file)[0])


_RENAME = _impact(_CU, lambda s: s.replace("role", "user_role"))
_DEFAULT = _impact(_CU, lambda s: s.replace('"viewer"', '"member"'))
_REMOVED = classify_change(_RM, None)
_RM_PARAM = _impact(_Q["UserService.add_member"], lambda s: s.replace(", active: bool = True", ""))
_ADD_SEC = _SEC[("API Reference", "Users", "UserService.remove_member")]


def _run(impact, unit, section):
    v = verify_section(impact, unit, section, _LLM)
    r = repair_section(v, impact, unit, section, _LLM)
    val = validate_repair(r, v)
    level, action = decide(v, r, val, _CFG)
    return v, r, val, level, action


def _action(impact, unit, section):
    return _run(impact, unit, section)[4].value


def _repaired(impact, unit, section):
    return _run(impact, unit, section)[1].repaired_content


def _unrelated_line_preserved():
    r = _run(_RENAME, _CU, _CU_SEC)[1]
    o = r.original_content.splitlines()
    n = r.repaired_content.splitlines()
    # the prose line mentioning bare "role" (the dict field, not the param) is untouched
    prose = [i for i, ln in enumerate(o) if "returns a dictionary" in ln][0]
    return o[prose] == n[prose]


SCENARIOS = [
    # ---- predefined (brief §22) ----
    Scenario("P4-01", 4, "Parameter rename correction -> auto_fix + `user_role`", "role->user_role",
             (True, "auto_fix"),
             lambda: ("`user_role`" in _repaired(_RENAME, _CU, _CU_SEC),
                      _action(_RENAME, _CU, _CU_SEC))),
    Scenario("P4-02", 4, "Default-value correction -> auto_fix + member", "viewer->member",
             (True, "auto_fix"),
             lambda: ("member" in _repaired(_DEFAULT, _CU, _CU_SEC),
                      _action(_DEFAULT, _CU, _CU_SEC))),
    Scenario("P4-03", 4, "Removed feature -> human_review (no destructive auto-edit)", "delete remove_member",
             "human_review", lambda: _action(_REMOVED, _RM, _RM_SEC)),
    Scenario("P4-04", 4, "Complex change (param removed) -> human_review", "drop add_member param",
             "human_review", lambda: _action(_RM_PARAM, _Q["UserService.add_member"], _ADD_SEC)),
    Scenario("P4-05", 4, "Unrelated paragraph preserved byte-identical", "rename repair",
             True, _unrelated_line_preserved),
    Scenario("P4-06", 4, "Heading preservation (style_ok) on rename", "rename repair",
             True, lambda: _run(_RENAME, _CU, _CU_SEC)[2].style_ok),
    Scenario("P4-07", 4, "Formatting preserved (scope_ok, same line count)", "rename repair",
             True, lambda: _run(_RENAME, _CU, _CU_SEC)[2].scope_ok),

    # ---- orchestrator-added ----
    Scenario("P4-08", 4, "[regression] validation ok for rename", "rename repair",
             True, lambda: _run(_RENAME, _CU, _CU_SEC)[2].ok, kind="orchestrator"),
    Scenario("P4-09", 4, "[edge] rename repair changes exactly the two backticked refs", "count diff lines",
             1, lambda: sum(1 for o, n in zip(
                 _run(_RENAME, _CU, _CU_SEC)[1].original_content.splitlines(),
                 _run(_RENAME, _CU, _CU_SEC)[1].repaired_content.splitlines()) if o != n),
             kind="orchestrator"),
    Scenario("P4-10", 4, "[negative] removal produces no auto-applied edit", "removal repair.changed",
             False, lambda: _run(_REMOVED, _RM, _RM_SEC)[1].changed, kind="orchestrator"),
    Scenario("P4-11", 4, "[regression] auto_fix reserved for HIGH confidence + low risk", "rename level",
             "high", lambda: _run(_RENAME, _CU, _CU_SEC)[3].value, kind="orchestrator"),
    Scenario("P4-12", 4, "[edge] tightening high threshold demotes auto_fix to review", "high_confidence=0.99",
             "human_review",
             lambda: decide(*_run(_DEFAULT, _CU, _CU_SEC)[:3], load_settings(high_confidence=0.99))[1].value,
             kind="orchestrator"),
    Scenario("P4-13", 4, "[security] no line without a `role` ref is altered", "rename repair",
             True, lambda: all(
                 o == n for o, n in zip(
                     _run(_RENAME, _CU, _CU_SEC)[1].original_content.splitlines(),
                     _run(_RENAME, _CU, _CU_SEC)[1].repaired_content.splitlines())
                 if "`role`" not in o), kind="orchestrator"),
]
