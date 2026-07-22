"""Targeted documentation repair.

Delegates to the LLM provider's `repair_section` (surgical, span-local edits) and
attaches a unified diff. The provider is responsible for preserving unaffected
text; the validator (validate.py) independently checks that it did.
"""

from __future__ import annotations

import difflib

from docguard.models import ChangeImpact, CodeUnit, DocSection, Repair, StalenessVerdict
from docguard.providers.base import LLMProvider


def repair_section(
    verdict: StalenessVerdict,
    impact: ChangeImpact,
    code_unit: CodeUnit,
    section: DocSection,
    llm: LLMProvider,
) -> Repair:
    repair = llm.repair_section(verdict=verdict, impact=impact, code_unit=code_unit, section=section)
    if repair.changed and not repair.unified_diff:
        repair = repair.model_copy(update={"unified_diff": _diff(section.doc_path, repair)})
    return repair


def _diff(path: str, repair: Repair) -> str:
    return "".join(
        difflib.unified_diff(
            repair.original_content.splitlines(keepends=True),
            repair.repaired_content.splitlines(keepends=True),
            fromfile=f"a/{path}", tofile=f"b/{path}",
        )
    )
