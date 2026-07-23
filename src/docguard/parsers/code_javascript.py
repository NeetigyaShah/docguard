# Neetigya, 2026-07-23: new file — JavaScript/JSX extractor (universal-parser feature).
"""JavaScript semantic parser -> CodeUnit list, via tree-sitter.

Extracts top-level functions, classes + their methods, and `const`/`let`/`var`
arrow-function (and function-expression) assignments. Params and defaults come
from the real grammar so change detection is language-agnostic. Never raises:
returns [] on unexpected input (CI safety).
"""

from __future__ import annotations

from typing import Any

from docguard.models import CodeUnit, CodeUnitKind, Param
from docguard.parsers._treesitter import first_child, node_text, parse_tree

_FN_VALUES = ("arrow_function", "function_expression", "generator_function")
_FN_DECLS = ("function_declaration", "generator_function_declaration")


def _clean_doc(text: str) -> str:
    """Strip JSDoc markers (/** */ and leading *) from a block comment."""
    t = text.strip()
    if not t.startswith("/**"):
        return ""
    t = t[3:]
    if t.endswith("*/"):
        t = t[:-2]
    lines = []
    for raw in t.splitlines():
        line = raw.strip()
        if line.startswith("*"):
            line = line[1:].strip()
        lines.append(line)
    return "\n".join(lines).strip()


def _doc(node: Any, src: bytes) -> str:
    prev = node.prev_sibling
    if prev is not None and prev.type == "comment":
        return _clean_doc(node_text(prev, src))
    return ""


def _sig(fn: Any, src: bytes) -> str:
    fp = first_child(fn, "formal_parameters")
    if fp is not None:
        return node_text(fp, src)
    ident = first_child(fn, "identifier")  # arrow with a single bare param: x => x
    if ident is not None:
        return "(" + node_text(ident, src) + ")"
    return "()"


def _params(fn: Any, src: bytes) -> list[Param]:
    fp = first_child(fn, "formal_parameters")
    if fp is None:
        ident = first_child(fn, "identifier")
        if ident is not None:
            nm = node_text(ident, src)
            if nm != "this":
                return [Param(name=nm, default=None)]
        return []
    out: list[Param] = []
    for c in fp.children:
        if c.type == "identifier":
            nm = node_text(c, src)
            if nm != "this":
                out.append(Param(name=nm, default=None))
        elif c.type == "assignment_pattern":
            idn = first_child(c, "identifier")
            if idn is None:  # destructured default (e.g. {a} = {}) -> unnameable
                continue
            default = None
            seen_eq = False
            for cc in c.children:
                if cc.type == "=":
                    seen_eq = True
                elif seen_eq:
                    default = node_text(cc, src)
                    break
            nm = node_text(idn, src)
            if nm != "this":
                out.append(Param(name=nm, default=default))
        elif c.type == "rest_pattern":
            idn = first_child(c, "identifier")
            if idn is not None:
                out.append(Param(name=node_text(idn, src), default=None))
        # object_pattern / array_pattern: destructured, cannot name -> skip
    return out


def _unit(
    node: Any, fn: Any, name: str, qual: str, kind: CodeUnitKind, doc: str,
    src: bytes, path: str, extra: tuple[str, ...] = (),
) -> CodeUnit:
    is_class = kind is CodeUnitKind.CLASS
    sig = "" if is_class else _sig(fn, src)
    params = [] if is_class else _params(fn, src)
    names = [p.name for p in params]
    return CodeUnit(
        id=CodeUnit.make_id(path, qual, kind),
        kind=kind, name=name, qualified_name=qual, signature=sig,
        docstring=doc, file=path,
        start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
        source=node_text(node, src),
        symbols=sorted({name, *names, *extra}), params=params,
    )


def parse_source(source: str, path: str) -> list[CodeUnit]:
    try:
        tree = parse_tree(source, "javascript")
    except Exception:
        return []
    try:
        src = source.encode("utf-8")
        units: list[CodeUnit] = []
        for stmt in tree.root_node.children:
            decl = stmt
            if stmt.type == "export_statement":
                inner = first_child(
                    stmt, *_FN_DECLS, "class_declaration",
                    "lexical_declaration", "variable_declaration",
                )
                if inner is None:
                    continue
                decl = inner

            if decl.type in _FN_DECLS:
                ident = first_child(decl, "identifier")
                if ident is None:
                    continue
                nm = node_text(ident, src)
                units.append(_unit(decl, decl, nm, nm, CodeUnitKind.FUNCTION, _doc(stmt, src), src, path))
            elif decl.type == "class_declaration":
                cident = first_child(decl, "identifier")
                if cident is None:
                    continue
                cname = node_text(cident, src)
                units.append(_unit(decl, decl, cname, cname, CodeUnitKind.CLASS, _doc(stmt, src), src, path))
                body = first_child(decl, "class_body")
                if body is not None:
                    for item in body.children:
                        if item.type != "method_definition":
                            continue
                        mident = first_child(item, "property_identifier")
                        if mident is None:
                            continue
                        mname = node_text(mident, src)
                        qual = f"{cname}.{mname}"
                        units.append(
                            _unit(item, item, mname, qual, CodeUnitKind.METHOD,
                                  _doc(item, src), src, path, extra=(cname,))
                        )
            elif decl.type in ("lexical_declaration", "variable_declaration"):
                for dtor in decl.children:
                    if dtor.type != "variable_declarator":
                        continue
                    fn = first_child(dtor, *_FN_VALUES)
                    ident = first_child(dtor, "identifier")
                    if fn is None or ident is None:
                        continue
                    nm = node_text(ident, src)
                    units.append(_unit(dtor, fn, nm, nm, CodeUnitKind.FUNCTION, _doc(stmt, src), src, path))
        return units
    except Exception:
        return []
