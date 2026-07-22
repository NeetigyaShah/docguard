"""Provider interfaces: embeddings and LLM.

Real providers (OpenAI/Anthropic/Chroma) and deterministic mocks all implement
these. The pipeline only ever depends on the interface, never a concrete class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from docguard.models import ChangeImpact, CodeUnit, DocSection, Repair, StalenessVerdict


class EmbeddingProvider(ABC):
    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text. Deterministic for a given text."""


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.calls = 0

    @abstractmethod
    def verify_staleness(
        self, *, impact: ChangeImpact, code_unit: CodeUnit, section: DocSection
    ) -> StalenessVerdict:
        """Decide whether `section` is stale w.r.t. the change in `code_unit`."""

    @abstractmethod
    def repair_section(
        self,
        *,
        verdict: StalenessVerdict,
        impact: ChangeImpact,
        code_unit: CodeUnit,
        section: DocSection,
    ) -> Repair:
        """Produce a targeted correction that only touches stale content."""
