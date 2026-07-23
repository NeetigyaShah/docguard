# Neetigya, 2026-07-23: new file — TypeScript/TSX extractor (universal-parser feature).
"""TypeScript → CodeUnit list, via tree-sitter (grammar 'typescript' / 'tsx').

Extracts top-level functions, classes, class methods, and const/let arrow (or
function-expression) assignments — each with structured params (name + default,
type annotations stripped) so change detection is language-agnostic. Never
raises: any malformed input degrades to [].
"""

from __future__ import annotations

from typing import Any

from docguard.models import CodeUnit, CodeUnitKind, Param
from docguard.parsers._treesitter import first_child, node_text, parse_tree

_PARAM_TYPES = ("required_parameter", "optional_parameter")
_FUNC_VALUES = ("arrow_function", "function_expression")


def _grammar(path: str) -> str:
    return "tsx" if path.endswith(".tsx") else "typescript"


def _clean_jsdoc(text: str) -> str:
    t = text.strip()
    if not (t.startswith("/**") and t.endswith("*/")):
        return ""  # only JSDoc blocks count as docstrings
    lines = []
    for ln in t[3:-2].splitlines():
        ln = ln.strip()
        if ln.startswith("*"):
            ln = ln[1:].strip()
        lines.append(ln)
    return "\n".join(lines).strip()


def _docstring(node: Any, src: bytes) -> str:
    prev = node.prev_sibling
    if prev is not None and prev.type == "comment":
        return _clean_jsdoc(node_text(prev, src))
    return ""


def _param_name(p: Any, src: bytes) -> str | None:
    ident = first_child(p, "identifier")
    if ident is not None:
        return node_text(ident, src)
    rest = first_child(p, "rest_pattern")  # ...rest
    if rest is not None:
        i = first_child(rest, "identifier")
        if i is not None:
            return node_text(i, src)
    return None  # destructured / `this` / unnamed -> skip


def _param_default(p: Any, src: bytes) -> str | None:
    kids = p.children
    for idx, c in enumerate(kids):
        if c.type == "=" and idx + 1 < len(kids):
            return node_text(kids[idx + 1], src)
    return None


def _params(fp: Any, src: bytes) -> list[Param]:
    out: list[Param] = []
    for p in fp.children:
        if p.type not in _PARAM_TYPES:
            continue
        name = _param_name(p, src)
        if name is None or name == "this":
            continue
        out.append(Param(name=name, default=_param_default(p, src)))
    return out


def _signature(fp: Any | None, src: bytes) -> str:
    return node_text(fp, src) if fp is not None else "()"


def _make(
    node: Any,
    src: bytes,
    path: str,
    name: str,
    qual: str,
    kind: CodeUnitKind,
    fp: Any | None,
    doc_anchor: Any,
    extra_symbols: tuple[str, ...] = (),
) -> CodeUnit:
    params = _params(fp, src) if fp is not None else []
    names = [p.name for p in params]
    return CodeUnit(
        id=CodeUnit.make_id(path, qual, kind),
        kind=kind,
        name=name,
        qualified_name=qual,
        signature=_signature(fp, src) if kind is not CodeUnitKind.CLASS else "",
        docstring=_docstring(doc_anchor, src),
        file=path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        source=node_text(node, src),
        symbols=sorted({name, *names, *extra_symbols}),
        params=params,
    )


def _arrow_fp(value: Any) -> Any | None:
    """formal_parameters of an arrow/function expression, or a synthetic-less None."""
    return first_child(value, "formal_parameters")


def _emit_class(cls: Any, src: bytes, path: str, doc_anchor: Any, units: list[CodeUnit]) -> None:
    name_node = first_child(cls, "type_identifier")
    if name_node is None:
        return
    cname = node_text(name_node, src)
    units.append(_make(cls, src, path, cname, cname, CodeUnitKind.CLASS, None, doc_anchor))
    body = first_child(cls, "class_body")
    if body is None:
        return
    for m in body.children:
        if m.type != "method_definition":
            continue
        pid = first_child(m, "property_identifier")
        if pid is None:
            continue
        mname = node_text(pid, src)
        fp = first_child(m, "formal_parameters")
        units.append(
            _make(m, src, path, mname, f"{cname}.{mname}", CodeUnitKind.METHOD, fp, m, (cname,))
        )


def _emit_lexical(decl: Any, src: bytes, path: str, doc_anchor: Any, units: list[CodeUnit]) -> None:
    for d in decl.children:
        if d.type != "variable_declarator":
            continue
        name_node = first_child(d, "identifier")
        value = first_child(d, *_FUNC_VALUES)
        if name_node is None or value is None:
            continue
        fname = node_text(name_node, src)
        fp = _arrow_fp(value)
        unit = _make(d, src, path, fname, fname, CodeUnitKind.FUNCTION, fp, doc_anchor)
        if fp is None and value.type == "arrow_function":
            # parenless single-arg arrow: `x => ...` has no formal_parameters;
            # the sole param is a bare identifier sibling of `=>`.
            ident = first_child(value, "identifier")
            if ident is not None:
                nm = node_text(ident, src)
                unit.params = [Param(name=nm)]
                unit.signature = f"({nm})"
                unit.symbols = sorted({*unit.symbols, nm})
        units.append(unit)


def _emit_function(fn: Any, src: bytes, path: str, doc_anchor: Any, units: list[CodeUnit]) -> None:
    name_node = first_child(fn, "identifier")
    if name_node is None:
        return
    fname = node_text(name_node, src)
    fp = first_child(fn, "formal_parameters")
    units.append(_make(fn, src, path, fname, fname, CodeUnitKind.FUNCTION, fp, doc_anchor))


def parse_source(source: str, path: str) -> list[CodeUnit]:
    try:
        tree = parse_tree(source, _grammar(path))
    except Exception:
        return []
    src = bytes(source, "utf-8")
    units: list[CodeUnit] = []
    for stmt in tree.root_node.children:
        # export/default wrapper: the doc comment sits above the wrapper.
        inner = stmt
        if stmt.type == "export_statement":
            inner = first_child(
                stmt, "function_declaration", "class_declaration", "lexical_declaration",
                "variable_declaration",
            )
            if inner is None:
                continue
        if inner.type == "function_declaration":
            _emit_function(inner, src, path, stmt, units)
        elif inner.type == "class_declaration":
            _emit_class(inner, src, path, stmt, units)
        elif inner.type in ("lexical_declaration", "variable_declaration"):
            _emit_lexical(inner, src, path, stmt, units)
    return units
