# Neetigya, 2026-07-23: new file — Java extractor (universal-parser feature).
"""Java semantic parser → CodeUnit list, via tree-sitter (`java` grammar).

Extracts top-level type declarations (class/interface/enum/record) and their
directly-declared methods, mirroring the CodeUnit shape built by
`code_python.py`. Java params carry no default (always None); the param NAME is
the trailing identifier of each formal/spread parameter. Never raises — returns
[] on unexpected input so one bad file can't break a CI run.
"""

from __future__ import annotations

from typing import Any

from docguard.models import CodeUnit, CodeUnitKind, Param
from docguard.parsers._treesitter import first_child, node_text, parse_tree

_TYPE_DECLS = (
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
)
_BODIES = ("class_body", "interface_body", "enum_body", "record_declaration_body")


def _clean_doc(text: str) -> str:
    """Strip Javadoc comment markers from a `/** ... */` block."""
    body = text.strip()
    if body.startswith("/**"):
        body = body[3:]
    elif body.startswith("/*"):
        body = body[2:]
    if body.endswith("*/"):
        body = body[:-2]
    lines = [line.strip().lstrip("*").strip() for line in body.splitlines()]
    return "\n".join(lines).strip()


def _leading_doc(node: Any, src: bytes) -> str:
    prev = node.prev_sibling
    if prev is not None and prev.type == "block_comment":
        txt = node_text(prev, src)
        if txt.lstrip().startswith("/**"):
            return _clean_doc(txt)
    return ""


def _param_name(param: Any, src: bytes) -> str | None:
    """Trailing identifier of a formal/spread parameter (the param name)."""
    ident = first_child(param, "identifier")
    if ident is not None:
        return node_text(ident, src)
    vd = first_child(param, "variable_declarator")  # spread_parameter: int... name
    if vd is not None:
        vid = first_child(vd, "identifier")
        if vid is not None:
            return node_text(vid, src)
    return None


def _params(method: Any, src: bytes) -> list[Param]:
    fp = first_child(method, "formal_parameters")
    if fp is None:
        return []
    out: list[Param] = []
    for c in fp.children:
        if c.type in ("formal_parameter", "spread_parameter"):
            name = _param_name(c, src)
            if name:
                out.append(Param(name=name, default=None))
    return out


def _members(body: Any) -> list[Any]:
    """Body members, unwrapping enum_body_declarations (methods live inside it)."""
    out: list[Any] = []
    for c in body.children:
        if c.type == "enum_body_declarations":
            out.extend(c.children)
        else:
            out.append(c)
    return out


def _signature(method: Any, src: bytes) -> str:
    fp = first_child(method, "formal_parameters")
    return node_text(fp, src) if fp is not None else "()"


def _make(node: Any, name: str, qual: str, kind: CodeUnitKind, path: str,
          src: bytes, params: list[Param], extra: tuple[str, ...] = ()) -> CodeUnit:
    is_func = kind in (CodeUnitKind.METHOD, CodeUnitKind.FUNCTION)
    names = [p.name for p in params]
    return CodeUnit(
        id=CodeUnit.make_id(path, qual, kind),
        kind=kind,
        name=name,
        qualified_name=qual,
        signature=_signature(node, src) if is_func else "",
        docstring=_leading_doc(node, src),
        file=path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        source=node_text(node, src),
        symbols=sorted({name, *names, *extra}),
        params=params,
    )


def parse_source(source: str, path: str) -> list[CodeUnit]:
    try:
        src = bytes(source, "utf-8")
        tree = parse_tree(source, "java")
        units: list[CodeUnit] = []
        for node in tree.root_node.children:
            if node.type not in _TYPE_DECLS:
                continue
            cname_node = first_child(node, "identifier")
            if cname_node is None:
                continue
            cname = node_text(cname_node, src)
            units.append(_make(node, cname, cname, CodeUnitKind.CLASS, path, src, []))
            body = first_child(node, *_BODIES)
            if body is None:
                continue
            for item in _members(body):
                if item.type != "method_declaration":
                    continue
                mname_node = first_child(item, "identifier")
                if mname_node is None:
                    continue
                mname = node_text(mname_node, src)
                qual = f"{cname}.{mname}"
                params = _params(item, src)
                units.append(
                    _make(item, mname, qual, CodeUnitKind.METHOD, path, src, params, (cname,))
                )
        return units
    except Exception:  # never crash a CI run on one bad file
        return []
