"""Confidence policy: verdict + validation → confidence level → action.

HIGH   → auto-fix eligible (simple, deterministic, validated correction).
MEDIUM → propose correction, require human review.
LOW    → report the discrepancy only; do not modify.

Thresholds are configurable via Settings (high_confidence, medium_confidence).
"""

from __future__ import annotations

from docguard.config import Settings
from docguard.models import (
    Action,
    ConfidenceLevel,
    Repair,
    RiskLevel,
    StalenessVerdict,
    ValidationResult,
)

_ACTION = {
    ConfidenceLevel.HIGH: Action.AUTO_FIX,
    ConfidenceLevel.MEDIUM: Action.HUMAN_REVIEW,
    ConfidenceLevel.LOW: Action.REPORT,
}


def decide(
    verdict: StalenessVerdict,
    repair: Repair | None,
    validation: ValidationResult | None,
    settings: Settings,
) -> tuple[ConfidenceLevel, Action]:
    conf = verdict.confidence

    # cannot safely auto-apply: failed validation, no surgical change, or high-risk edit
    unsafe = (
        validation is None
        or not validation.ok
        or repair is None
        or not repair.changed
        or verdict.risk == RiskLevel.HIGH
    )

    if unsafe:
        level = ConfidenceLevel.MEDIUM if conf >= settings.medium_confidence else ConfidenceLevel.LOW
    elif conf >= settings.high_confidence and verdict.risk == RiskLevel.LOW:
        level = ConfidenceLevel.HIGH
    elif conf >= settings.medium_confidence:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    return level, _ACTION[level]
