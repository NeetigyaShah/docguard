"""Shared domain models — the contract every pipeline stage speaks.

Kept deliberately small and typed. Every stage consumes and produces these;
nothing crosses a module boundary that isn't one of these types.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, Field


def stable_hash(*parts: str) -> str:
    """Short deterministic id from arbitrary string parts."""
    h = hashlib.sha1("\x00".join(parts).encode("utf-8"))  # noqa: S324 (id only, not security)
    return h.hexdigest()[:12]


# --------------------------------------------------------------------------- #
# Phase 1 — code + doc understanding
# --------------------------------------------------------------------------- #
class CodeUnitKind(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    CONFIG_KEY = "config_key"
    CLI_COMMAND = "cli_command"
    ENDPOINT = "endpoint"


class CodeUnit(BaseModel):
    """A semantic unit of source code with a stable id."""

    id: str
    kind: CodeUnitKind
    name: str
    qualified_name: str
    signature: str = ""
    docstring: str = ""
    file: str
    start_line: int
    end_line: int
    source: str = ""
    symbols: list[str] = Field(default_factory=list)

    @staticmethod
    def make_id(file: str, qualified_name: str, kind: CodeUnitKind) -> str:
        # Readable + stable: survives line moves, changes only on rename/relocate.
        return f"{file}::{qualified_name}::{kind.value}"


class DocSection(BaseModel):
    """A Markdown section keyed by its nested heading path."""

    id: str
    doc_path: str
    heading: str
    heading_path: list[str] = Field(default_factory=list)
    level: int = 0
    content: str = ""
    start_line: int = 0
    end_line: int = 0
    referenced_symbols: list[str] = Field(default_factory=list)

    @staticmethod
    def make_id(doc_path: str, heading_path: list[str]) -> str:
        return f"{doc_path}#" + "/".join(heading_path)


class MapMethod(str, Enum):
    EXACT = "exact"
    LEXICAL = "lexical"
    EMBEDDING = "embedding"


class DocLink(BaseModel):
    """A scored link between a code unit and a doc section."""

    code_unit_id: str
    doc_section_id: str
    score: float
    method: MapMethod


# --------------------------------------------------------------------------- #
# Phase 2 — change detection
# --------------------------------------------------------------------------- #
class ChangeKind(str, Enum):
    # low-significance (down-ranked)
    WHITESPACE = "whitespace"
    COMMENT = "comment"
    FORMATTING = "formatting"
    TEST_ONLY = "test_only"
    INTERNAL_REFACTOR = "internal_refactor"
    # high-significance (documentation-relevant)
    SIGNATURE_CHANGE = "signature_change"
    PARAM_RENAMED = "param_renamed"
    PARAM_REMOVED = "param_removed"
    PARAM_ADDED = "param_added"
    DEFAULT_CHANGED = "default_changed"
    PUBLIC_API_CHANGE = "public_api_change"
    REMOVED_PUBLIC = "removed_public"
    ENDPOINT_CHANGE = "endpoint_change"
    CONFIG_CHANGE = "config_change"
    CLI_CHANGE = "cli_change"
    CAPABILITY_ADDED = "capability_added"
    CAPABILITY_REMOVED = "capability_removed"


HIGH_SIGNIFICANCE: set[ChangeKind] = {
    ChangeKind.SIGNATURE_CHANGE,
    ChangeKind.PARAM_RENAMED,
    ChangeKind.PARAM_REMOVED,
    ChangeKind.PARAM_ADDED,
    ChangeKind.DEFAULT_CHANGED,
    ChangeKind.PUBLIC_API_CHANGE,
    ChangeKind.REMOVED_PUBLIC,
    ChangeKind.ENDPOINT_CHANGE,
    ChangeKind.CONFIG_CHANGE,
    ChangeKind.CLI_CHANGE,
    ChangeKind.CAPABILITY_ADDED,
    ChangeKind.CAPABILITY_REMOVED,
}


class ChangeImpact(BaseModel):
    """A classified change to one code unit (or file-level fallback)."""

    file: str
    code_unit_id: str | None = None
    unit_name: str = ""
    kind: CodeUnitKind | None = None
    old_source: str = ""
    new_source: str = ""
    change_kinds: list[ChangeKind] = Field(default_factory=list)
    meaningful: bool = False
    significance: float = 0.0  # 0..1
    summary: str = ""

    @property
    def is_high_significance(self) -> bool:
        return any(k in HIGH_SIGNIFICANCE for k in self.change_kinds)


# --------------------------------------------------------------------------- #
# Phase 3 — staleness
# --------------------------------------------------------------------------- #
class StalenessLabel(str, Enum):
    STALE = "stale"
    ACCURATE = "accurate"
    UNRELATED = "unrelated"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StalenessVerdict(BaseModel):
    doc_section_id: str
    code_unit_id: str
    label: StalenessLabel
    confidence: float  # 0..1
    reason: str = ""
    stale_claims: list[str] = Field(default_factory=list)
    correction_scope: str = ""
    risk: RiskLevel = RiskLevel.LOW


# --------------------------------------------------------------------------- #
# Phase 4 — repair, validation, confidence
# --------------------------------------------------------------------------- #
class Repair(BaseModel):
    doc_section_id: str
    original_content: str
    repaired_content: str
    unified_diff: str = ""
    rationale: str = ""
    changed: bool = False


class ValidationResult(BaseModel):
    ok: bool
    factual_ok: bool = True
    scope_ok: bool = True
    style_ok: bool = True
    issues: list[str] = Field(default_factory=list)


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Action(str, Enum):
    AUTO_FIX = "auto_fix"
    HUMAN_REVIEW = "human_review"
    REPORT = "report"


class SectionResult(BaseModel):
    """Everything decided about one candidate doc section."""

    section: DocSection
    code_unit_id: str
    verdict: StalenessVerdict
    repair: Repair | None = None
    validation: ValidationResult | None = None
    confidence: ConfidenceLevel | None = None
    action: Action | None = None


# --------------------------------------------------------------------------- #
# Pipeline result (also the dashboard/audit payload)
# --------------------------------------------------------------------------- #
class PipelineResult(BaseModel):
    repo: str = ""
    base: str = ""
    head: str = ""
    sections_verified_accurate: int = 0
    sections_stale: int = 0
    autofixes_generated: int = 0
    review_needed: int = 0
    results: list[SectionResult] = Field(default_factory=list)
    llm_calls: int = 0
    notes: list[str] = Field(default_factory=list)
