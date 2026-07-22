"""Staleness verification.

For each meaningful change, gathers its mapped candidate doc sections and asks
the LLM provider (mock or real) for a structured verdict. The provider receives
only the minimal context (old/new code via the impact, change kinds, the one
section). Guardrails keep STALE verdicts grounded; untrusted repo text is
delimited inside the real provider's prompt (see providers/real.py).
"""

from __future__ import annotations

from docguard.mapping.mapper import sections_for_unit
from docguard.models import (
    ChangeImpact,
    CodeUnit,
    DocLink,
    DocSection,
    SectionResult,
    StalenessLabel,
    StalenessVerdict,
)
from docguard.providers.base import LLMProvider


def verify_section(
    impact: ChangeImpact, code_unit: CodeUnit, section: DocSection, llm: LLMProvider
) -> StalenessVerdict:
    verdict = llm.verify_staleness(impact=impact, code_unit=code_unit, section=section)
    # grounding guardrail: an ungrounded STALE claim is not trusted
    if verdict.label == StalenessLabel.STALE and not verdict.stale_claims and not verdict.reason:
        return verdict.model_copy(update={"confidence": min(verdict.confidence, 0.4)})
    return verdict


def verify_changes(
    impacts: list[ChangeImpact],
    units_by_id: dict[str, CodeUnit],
    sections_by_id: dict[str, DocSection],
    links: list[DocLink],
    llm: LLMProvider,
) -> list[SectionResult]:
    """Verify every meaningful change against its candidate sections."""
    results: list[SectionResult] = []
    seen: set[tuple[str, str]] = set()
    for impact in impacts:
        if not impact.meaningful or not impact.code_unit_id:
            continue
        unit = units_by_id.get(impact.code_unit_id)
        if unit is None:
            continue
        for sid in sections_for_unit(unit.id, links):
            section = sections_by_id.get(sid)
            if section is None or (unit.id, sid) in seen:
                continue
            seen.add((unit.id, sid))
            verdict = verify_section(impact, unit, section, llm)
            results.append(SectionResult(section=section, code_unit_id=unit.id, verdict=verdict))
    return results
