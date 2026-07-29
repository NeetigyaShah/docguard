"""Regressions for the deployable paths (GitHub Action / self-host Docker).

Covers three bugs that only show up when DocGuard runs against a *real* repo:
1. auto-fix PRs used to push EMPTY file content (truncating the docs).
2. a UTF-8 BOM made every parser return zero units -> silent "no changes".
3. `auto-fix: false` was accepted as an input but never actually enforced.
"""

from docguard.github.integration import plan_actions, run
from docguard.models import (
    Action,
    ConfidenceLevel,
    DocSection,
    PipelineResult,
    Repair,
    RiskLevel,
    SectionResult,
    StalenessLabel,
    StalenessVerdict,
    ValidationResult,
)
from docguard.parsers.code import parse_code_source
from docguard.parsers.docs_markdown import parse_markdown_source

DOC = "# API\n\n## create_user\n\nThe `create_user` function accepts `role`.\n"


def _autofix_result(repo: str) -> PipelineResult:
    section = DocSection(
        id="docs/api.md#API/create_user", doc_path="docs/api.md", heading="create_user",
        heading_path=["API", "create_user"], content="The `create_user` function accepts `role`.",
    )
    return PipelineResult(
        repo=repo, sections_stale=1, autofixes_generated=1,
        results=[SectionResult(
            section=section, code_unit_id="cu",
            verdict=StalenessVerdict(
                doc_section_id=section.id, code_unit_id="cu", label=StalenessLabel.STALE,
                confidence=0.92, reason="renamed", risk=RiskLevel.LOW),
            repair=Repair(
                doc_section_id=section.id,
                original_content="The `create_user` function accepts `role`.",
                repaired_content="The `create_user` function accepts `user_role`.",
                changed=True),
            validation=ValidationResult(ok=True),
            confidence=ConfidenceLevel.HIGH, action=Action.AUTO_FIX,
        )],
    )


def _repo(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "api.md").write_text(DOC, encoding="utf-8")
    return tmp_path


def test_autofix_edit_carries_full_patched_file(tmp_path):
    """The edit must be the whole file with only the stale span swapped."""
    root = _repo(tmp_path)
    plan = plan_actions(_autofix_result(str(root)))

    assert plan.mode == "pr"
    assert len(plan.file_edits) == 1
    new = plan.file_edits[0].new_content
    assert new, "empty content would truncate the doc file"
    assert new == DOC.replace("`role`", "`user_role`")
    assert "# API" in new and "## create_user" in new  # untouched text preserved


def test_unreadable_doc_falls_back_to_comment(tmp_path):
    """No file on disk -> never emit an empty edit; downgrade to a review comment."""
    plan = plan_actions(_autofix_result(str(tmp_path)))
    assert plan.mode == "comment"
    assert plan.file_edits == []


def test_auto_fix_false_downgrades_to_comment(tmp_path):
    root = _repo(tmp_path)
    status = run(_autofix_result(str(root)), token="", repo_slug="", auto_fix=False)
    assert status["mode"] == "comment"


def test_bom_prefixed_sources_still_parse():
    bom = "﻿"
    assert parse_code_source(bom + "def f(a, b=1):\n    return a\n", "m.py"), "BOM broke code parsing"
    assert parse_markdown_source(bom + DOC, "docs/api.md"), "BOM broke markdown parsing"
