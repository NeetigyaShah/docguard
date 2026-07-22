"""Deterministic, offline mock providers.

These make the entire pipeline runnable and testable with zero API keys. The
mock LLM is rule-driven: it inspects the *structured* change context and doc
text and returns a sensible verdict/repair. It is not "AI" — it is a
deterministic oracle designed so the fixtures produce real, reproducible
results. Real providers implement the same interface with an actual model.
"""

from __future__ import annotations

import difflib
import math
import re

from docguard.models import (
    ChangeImpact,
    ChangeKind,
    CodeUnit,
    DocSection,
    Repair,
    RiskLevel,
    StalenessLabel,
    StalenessVerdict,
)
from docguard.providers.base import EmbeddingProvider, LLMProvider

_DIM = 256
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


class MockEmbeddingProvider(EmbeddingProvider):
    """Hashing bag-of-tokens embedding. Cosine similarity ~ token overlap."""

    name = "mock"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * _DIM
        for tok in _tokens(text):
            idx = hash_token(tok) % _DIM
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def hash_token(tok: str) -> int:
    # stable across processes (Python's hash() is salted; this is not)
    h = 2166136261
    for ch in tok:
        h = (h ^ ord(ch)) * 16777619 & 0xFFFFFFFF
    return h


# --------------------------------------------------------------------------- #
# signature parsing helpers (shared by verify + repair)
# --------------------------------------------------------------------------- #
def parse_params(source: str) -> list[tuple[str, str | None]]:
    """Best-effort (name, default) pairs from the first def signature."""
    m = re.search(r"def\s+\w+\s*\((.*?)\)\s*(->|:)", source, re.S)
    if not m:
        return []
    inside = m.group(1)
    parts, depth, cur = [], 0, ""
    for ch in inside:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    out: list[tuple[str, str | None]] = []
    for p in parts:
        p = p.strip()
        if not p or p in ("self", "cls") or p.startswith(("*", "/")):
            continue
        name = p.split(":")[0].split("=")[0].strip()
        default = p.split("=", 1)[1].strip() if "=" in p else None
        out.append((name, default))
    return out


def _renames(old: str, new: str) -> list[tuple[str, str]]:
    o = [n for n, _ in parse_params(old)]
    n = [n for n, _ in parse_params(new)]
    removed = [x for x in o if x not in n]
    added = [x for x in n if x not in o]
    return list(zip(removed, added))  # positional pairing


def _default_changes(old: str, new: str) -> list[tuple[str, str, str]]:
    od = dict(parse_params(old))
    nd = dict(parse_params(new))
    out = []
    # same-name default changes
    for name, newdef in nd.items():
        if name in od and od[name] is not None and newdef is not None and od[name] != newdef:
            out.append((name, od[name], newdef))
    # default changes that ride along with a rename (old_name -> new_name)
    for old_name, new_name in _renames(old, new):
        ov, nv = od.get(old_name), nd.get(new_name)
        if ov is not None and nv is not None and ov != nv:
            out.append((new_name, ov, nv))
    return out


def _unquote(s: str) -> str:
    return s.strip().strip("'\"")


def _word_in(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


# --------------------------------------------------------------------------- #
# Mock LLM
# --------------------------------------------------------------------------- #
class MockLLMProvider(LLMProvider):
    name = "mock"

    def _related(self, code_unit: CodeUnit, section: DocSection) -> bool:
        if code_unit.name in section.referenced_symbols:
            return True
        content = section.content
        if _word_in(content, code_unit.name):
            return True
        return any(_word_in(content, s) for s in code_unit.symbols)

    def verify_staleness(
        self, *, impact: ChangeImpact, code_unit: CodeUnit, section: DocSection
    ) -> StalenessVerdict:
        self.calls += 1
        vid = dict(doc_section_id=section.id, code_unit_id=code_unit.id)
        content = section.content

        # 1) nothing publicly meaningful changed -> accurate
        if not impact.meaningful or not impact.is_high_significance:
            return StalenessVerdict(
                **vid,
                label=StalenessLabel.ACCURATE,
                confidence=0.9,
                reason="Change is internal/low-significance; public behavior unchanged.",
                risk=RiskLevel.LOW,
            )

        related = self._related(code_unit, section)

        # 2) removal of a documented feature
        if any(
            k in (ChangeKind.REMOVED_PUBLIC, ChangeKind.CAPABILITY_REMOVED)
            for k in impact.change_kinds
        ):
            if related:
                return StalenessVerdict(
                    **vid,
                    label=StalenessLabel.STALE,
                    confidence=0.8,
                    reason=f"`{code_unit.name}` was removed but documentation still describes it.",
                    stale_claims=[code_unit.name],
                    correction_scope="Remove or flag the description of the deleted feature.",
                    risk=RiskLevel.HIGH,
                )
            return StalenessVerdict(
                **vid, label=StalenessLabel.UNRELATED, confidence=0.8,
                reason="Removed symbol is not referenced by this section.",
            )

        # 3) unrelated to this section
        if not related:
            return StalenessVerdict(
                **vid,
                label=StalenessLabel.UNRELATED,
                confidence=0.8,
                reason="Section does not reference the changed code unit.",
            )

        # 4) renamed parameter whose OLD name appears in the docs
        for old_name, new_name in _renames(impact.old_source, impact.new_source):
            if _word_in(content, old_name):
                return StalenessVerdict(
                    **vid,
                    label=StalenessLabel.STALE,
                    confidence=0.92,
                    reason=f"Parameter `{old_name}` was renamed to `{new_name}`; docs still say `{old_name}`.",
                    stale_claims=[old_name],
                    correction_scope=f"Rename `{old_name}` -> `{new_name}`.",
                    risk=RiskLevel.LOW,
                )

        # 5) changed default whose OLD value is documented
        for name, old_def, new_def in _default_changes(impact.old_source, impact.new_source):
            uq = _unquote(old_def)
            if uq and _word_in(content, uq):
                return StalenessVerdict(
                    **vid,
                    label=StalenessLabel.STALE,
                    confidence=0.88,
                    reason=f"Default for `{name}` changed {old_def} -> {new_def}; docs still say {old_def}.",
                    stale_claims=[uq],
                    correction_scope=f"Update documented default {old_def} -> {new_def}.",
                    risk=RiskLevel.LOW,
                )

        # 6) removed parameter still documented
        for old_name, _new in [(o, None) for o in _params_removed(impact)]:
            if _word_in(content, old_name):
                return StalenessVerdict(
                    **vid,
                    label=StalenessLabel.STALE,
                    confidence=0.85,
                    reason=f"Parameter `{old_name}` was removed but is still documented.",
                    stale_claims=[old_name],
                    correction_scope=f"Remove references to `{old_name}`.",
                    risk=RiskLevel.MEDIUM,
                )

        # 7) related + meaningful but no concrete stale token found -> accurate (avoid FP)
        return StalenessVerdict(
            **vid,
            label=StalenessLabel.ACCURATE,
            confidence=0.6,
            reason="Related change, but no specific stale claim detected in the section text.",
            risk=RiskLevel.LOW,
        )

    def repair_section(
        self,
        *,
        verdict: StalenessVerdict,
        impact: ChangeImpact,
        code_unit: CodeUnit,
        section: DocSection,
    ) -> Repair:
        self.calls += 1
        original = section.content
        repaired = original

        # targeted swaps only — everything else stays byte-identical.
        # Param renames: only inside `backticks` (a bare word like "role" in prose
        # may name an unrelated field); default values: whole-word (values are specific).
        for old_name, new_name in _renames(impact.old_source, impact.new_source):
            repaired = re.sub(rf"`{re.escape(old_name)}`", f"`{new_name}`", repaired)
        for _name, old_def, new_def in _default_changes(impact.old_source, impact.new_source):
            uq_old, uq_new = _unquote(old_def), _unquote(new_def)
            if uq_old:
                repaired = re.sub(rf"\b{re.escape(uq_old)}\b", uq_new, repaired)

        changed = repaired != original
        diff = ""
        if changed:
            diff = "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    repaired.splitlines(keepends=True),
                    fromfile=f"a/{section.doc_path}",
                    tofile=f"b/{section.doc_path}",
                )
            )
        return Repair(
            doc_section_id=section.id,
            original_content=original,
            repaired_content=repaired,
            unified_diff=diff,
            rationale=verdict.correction_scope or verdict.reason,
            changed=changed,
        )


def _params_removed(impact: ChangeImpact) -> list[str]:
    o = [n for n, _ in parse_params(impact.old_source)]
    n = [n for n, _ in parse_params(impact.new_source)]
    # a rename consumes one removed+one added; only report pure removals
    renamed_old = {r for r, _ in _renames(impact.old_source, impact.new_source)}
    return [x for x in o if x not in n and x not in renamed_old]
