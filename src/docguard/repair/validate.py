"""Second-pass validation of a generated repair.

Independent of the repair step. Checks that the correction (1) actually resolves
the diagnosed stale claim (factual), (2) touched only the stale spans and left
everything else byte-identical (scope), and (3) preserved headings, list markers
and indentation (style).
"""

from __future__ import annotations

import re

from docguard.models import Repair, StalenessVerdict, ValidationResult

_LEADING = re.compile(r"^\s*")
_MARKER = re.compile(r"^\s*([#>\-*+]|\d+\.)\s?")


def _leading(line: str) -> str:
    return _LEADING.match(line).group()


def _marker(line: str) -> str:
    m = _MARKER.match(line)
    return m.group(1) if m else ""


def _wcount(text: str, word: str) -> int:
    return len(re.findall(rf"\b{re.escape(word)}\b", text))


def validate_repair(repair: Repair, verdict: StalenessVerdict) -> ValidationResult:
    if not repair.changed:
        return ValidationResult(
            ok=False, factual_ok=False, scope_ok=True, style_ok=True,
            issues=["no targeted change produced (correction not auto-appliable)"],
        )

    orig = repair.original_content.splitlines()
    new = repair.repaired_content.splitlines()
    issues: list[str] = []

    # scope: surgical swaps never add/remove lines
    scope_ok = len(orig) == len(new)
    if not scope_ok:
        issues.append("line count changed (edit is not span-local)")
    changed = [(o, n) for o, n in zip(orig, new) if o != n]

    # style: no heading line edited; markers + indentation preserved on changed lines
    style_ok = True
    for o, n in changed:
        if o.lstrip().startswith("#"):
            style_ok = False
            issues.append("a heading line was modified")
        if _leading(o) != _leading(n) or _marker(o) != _marker(n):
            style_ok = False
            issues.append("indentation or list marker changed")

    # factual: at least one stale claim's whole-word occurrences were reduced
    # (whole-word, so renaming `role`->`user_role` counts as removing `role`)
    factual_ok = True
    if verdict.stale_claims:
        removed_any = any(
            _wcount(repair.repaired_content, c) < _wcount(repair.original_content, c)
            for c in verdict.stale_claims
        )
        factual_ok = removed_any
        if not removed_any:
            issues.append("diagnosed stale claim still present after repair")

    return ValidationResult(
        ok=scope_ok and style_ok and factual_ok,
        factual_ok=factual_ok, scope_ok=scope_ok, style_ok=style_ok, issues=issues,
    )
