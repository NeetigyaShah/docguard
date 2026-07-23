"""Meaningful-change classification.

Compares parsed code units across two revisions and labels each impacted unit.
Down-ranks whitespace / comment / formatting / test-only / internal-refactor
changes; prioritizes signature / parameter / default / config / CLI / endpoint /
capability changes (the ones that can make docs stale).
"""

from __future__ import annotations

import ast
import io
import tokenize

from docguard.changes.diff import changed_files, file_at
from docguard.models import ChangeImpact, ChangeKind, CodeUnit, CodeUnitKind, Param
from docguard.parsers.code import CODE_EXTENSIONS, parse_code_source

# Neetigya, 2026-07-23: multi-language support. This module now imports the universal
# parser (parse_code_source / CODE_EXTENSIONS) instead of the Python-only parser, and
# `_sig_kinds` + classify_change were rewritten to diff structured `Param` lists instead
# of re-parsing source with a Python `def` regex.


def _comments(src: str) -> list[str]:
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readlines().__iter__().__next__)
        return [t.string for t in toks if t.type == tokenize.COMMENT]
    except Exception:
        return []


def _norm_ws(src: str) -> str:
    return "\n".join(line.rstrip() for line in src.splitlines()).strip()


def _same_ast(a: str, b: str) -> bool:
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except SyntaxError:
        return _norm_ws(a) == _norm_ws(b)


def _is_public(name: str) -> bool:
    return not name.split(".")[-1].split(":")[-1].startswith("_")


def _sig_kinds(old_params: list[Param], new_params: list[Param]) -> list[ChangeKind]:
    old = {p.name: p.default for p in old_params}
    new = {p.name: p.default for p in new_params}
    o, n = list(old), list(new)
    removed = [x for x in o if x not in n]
    added = [x for x in n if x not in o]
    kinds: list[ChangeKind] = []
    # positional rename: equal counts of removed/added
    renames = min(len(removed), len(added))
    if renames:
        kinds.append(ChangeKind.PARAM_RENAMED)
    if len(removed) > renames:
        kinds.append(ChangeKind.PARAM_REMOVED)
    if len(added) > renames:
        kinds.append(ChangeKind.PARAM_ADDED)
    for name in set(o) & set(n):
        if old[name] != new[name]:
            kinds.append(ChangeKind.DEFAULT_CHANGED)
            break
    return kinds


def _significance(kinds: list[ChangeKind]) -> float:
    from docguard.models import HIGH_SIGNIFICANCE

    if any(k in HIGH_SIGNIFICANCE for k in kinds):
        return 0.9
    if ChangeKind.INTERNAL_REFACTOR in kinds:
        return 0.2
    return 0.05


def classify_change(
    old_unit: CodeUnit | None, new_unit: CodeUnit | None, *, is_test: bool = False
) -> ChangeImpact | None:
    """Classify one unit's change. Returns None if nothing changed."""
    unit = new_unit or old_unit
    assert unit is not None
    old_src = old_unit.source if old_unit else ""
    new_src = new_unit.source if new_unit else ""
    old_params = old_unit.params if old_unit else []
    new_params = new_unit.params if new_unit else []
    kinds: list[ChangeKind] = []

    _structural = {
        CodeUnitKind.CONFIG_KEY: [ChangeKind.CONFIG_CHANGE],
        CodeUnitKind.CLI_COMMAND: [ChangeKind.CLI_CHANGE],
        CodeUnitKind.ENDPOINT: [ChangeKind.ENDPOINT_CHANGE],
    }
    if is_test:
        kinds = [ChangeKind.TEST_ONLY]
    elif old_unit and not new_unit:  # removed
        if unit.kind in _structural:
            kinds = list(_structural[unit.kind])
        elif _is_public(unit.qualified_name):
            kinds = [ChangeKind.REMOVED_PUBLIC, ChangeKind.CAPABILITY_REMOVED]
        else:
            kinds = [ChangeKind.INTERNAL_REFACTOR]
    elif new_unit and not old_unit:  # added
        if unit.kind in _structural:
            kinds = list(_structural[unit.kind])
        elif _is_public(unit.qualified_name):
            kinds = [ChangeKind.CAPABILITY_ADDED]
        else:
            kinds = [ChangeKind.INTERNAL_REFACTOR]
    else:  # modified
        if old_src == new_src:
            return None
        if unit.kind == CodeUnitKind.CONFIG_KEY:
            kinds = [ChangeKind.CONFIG_CHANGE]
        elif unit.kind == CodeUnitKind.CLI_COMMAND:
            kinds = [ChangeKind.CLI_CHANGE]
        elif _same_ast(old_src, new_src):
            kinds = [ChangeKind.COMMENT] if _comments(old_src) != _comments(new_src) else [ChangeKind.WHITESPACE]
        else:
            sig = _sig_kinds(old_params, new_params)
            if sig:
                kinds = [*sig, ChangeKind.SIGNATURE_CHANGE]
                if unit.kind == CodeUnitKind.ENDPOINT:
                    kinds.append(ChangeKind.ENDPOINT_CHANGE)
                elif _is_public(unit.qualified_name):
                    kinds.append(ChangeKind.PUBLIC_API_CHANGE)
            elif unit.kind == CodeUnitKind.ENDPOINT:
                kinds = [ChangeKind.ENDPOINT_CHANGE]
            else:
                kinds = [ChangeKind.INTERNAL_REFACTOR]

    from docguard.models import HIGH_SIGNIFICANCE

    meaningful = any(k in HIGH_SIGNIFICANCE for k in kinds)
    return ChangeImpact(
        file=unit.file, code_unit_id=unit.id, unit_name=unit.name, kind=unit.kind,
        old_source=old_src, new_source=new_src,
        old_params=old_params, new_params=new_params, change_kinds=kinds,
        meaningful=meaningful, significance=_significance(kinds),
        summary=f"{unit.qualified_name}: {', '.join(k.value for k in kinds)}",
    )


def _units_by_key(source: str, path: str) -> dict[tuple[str, CodeUnitKind], CodeUnit]:
    return {(u.qualified_name, u.kind): u for u in parse_code_source(source, path)}


def detect_changes(
    repo: str, base: str, head: str | None = None, src_paths: list[str] | None = None
) -> list[ChangeImpact]:
    """Full change detection between two revisions for any supported source file."""
    src_paths = src_paths or ["src"]
    impacts: list[ChangeImpact] = []
    for status, path in changed_files(repo, base, head):
        # Neetigya, 2026-07-23: was `if not path.endswith(".py")` — now accepts any
        # extension the universal parser handles (py / ts / tsx / js / jsx / java).
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in CODE_EXTENSIONS:
            continue
        if not any(path.startswith(sp.rstrip("/") + "/") or path.startswith(sp) for sp in src_paths):
            if "test" not in path:
                continue
        is_test = "test" in path.lower()
        old_units = _units_by_key(file_at(repo, base, path), path) if status != "A" else {}
        new_units = _units_by_key(file_at(repo, head, path), path) if status != "D" else {}
        for key in set(old_units) | set(new_units):
            impact = classify_change(old_units.get(key), new_units.get(key), is_test=is_test)
            if impact:
                impacts.append(impact)
    return impacts
