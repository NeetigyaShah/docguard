"""Python semantic parser → CodeUnit list, via the stdlib `ast` module.

Extracts functions, classes, methods, module-level config constants, argparse
CLI commands, and decorator-based HTTP endpoints, each with a stable id.
Parser interface is deliberately narrow so other languages / tree-sitter can be
added later as sibling `parse_<lang>_source` functions.
"""

from __future__ import annotations

import ast
from pathlib import Path

from docguard.models import CodeUnit, CodeUnitKind, Param

_ROUTE_ATTRS = {"get", "post", "put", "delete", "patch", "route"}


def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        return "(" + ast.unparse(node.args) + ")"
    except Exception:  # pragma: no cover - very old py
        return "()"


def _unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover
        return None


# Neetigya, 2026-07-23: added `_params` / `_unparse` so the Python parser emits
# structured `Param(name, default)` on every CodeUnit (see `make()` below), matching
# the new language-agnostic change-detection contract shared with the ts/js/java parsers.
def _params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[Param]:
    a = node.args
    pos = a.posonlyargs + a.args
    # defaults align to the TAIL of the positional args
    pos_defaults: list[ast.AST | None] = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    out: list[Param] = []
    for p, d in zip(pos, pos_defaults):
        if p.arg not in ("self", "cls"):
            out.append(Param(name=p.arg, default=_unparse(d)))
    for p, d in zip(a.kwonlyargs, a.kw_defaults):
        if p.arg not in ("self", "cls"):
            out.append(Param(name=p.arg, default=_unparse(d)))
    return out


def _param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [p.name for p in _params(node)]


def _endpoint_path(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr in _ROUTE_ATTRS:
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    return f"{dec.func.attr.upper()} {dec.args[0].value!s}"
    return None


def parse_python_source(source: str, file_path: str) -> list[CodeUnit]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    units: list[CodeUnit] = []

    def make(node, name, qual, kind, extra_symbols=()):
        seg = ast.get_source_segment(source, node) or ""
        is_func = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        sig = _sig(node) if is_func else ""
        param_objs = _params(node) if is_func else []
        names = [p.name for p in param_objs]
        return CodeUnit(
            id=CodeUnit.make_id(file_path, qual, kind),
            kind=kind, name=name, qualified_name=qual, signature=sig,
            docstring=ast.get_docstring(node) or "" if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else "",
            file=file_path, start_line=node.lineno, end_line=getattr(node, "end_lineno", node.lineno),
            source=seg, symbols=sorted({name, *names, *extra_symbols}), params=param_objs,
        )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            path = _endpoint_path(node)
            if path:
                units.append(make(node, node.name, path, CodeUnitKind.ENDPOINT, (node.name,)))
            else:
                units.append(make(node, node.name, node.name, CodeUnitKind.FUNCTION))
            units += _cli_commands(node, source, file_path)
        elif isinstance(node, ast.ClassDef):
            units.append(make(node, node.name, node.name, CodeUnitKind.CLASS))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qual = f"{node.name}.{item.name}"
                    units.append(make(item, item.name, qual, CodeUnitKind.METHOD, (node.name,)))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            units += _config_keys(node, source, file_path)
    return units


def _config_keys(node: ast.Assign | ast.AnnAssign, source: str, file_path: str) -> list[CodeUnit]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    out = []
    for t in targets:
        if isinstance(t, ast.Name):
            out.append(
                CodeUnit(
                    id=CodeUnit.make_id(file_path, t.id, CodeUnitKind.CONFIG_KEY),
                    kind=CodeUnitKind.CONFIG_KEY, name=t.id, qualified_name=t.id,
                    signature=(ast.get_source_segment(source, node) or "").strip(),
                    file=file_path, start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    source=ast.get_source_segment(source, node) or "", symbols=[t.id],
                )
            )
    return out


def _cli_commands(func_node, source: str, file_path: str) -> list[CodeUnit]:
    out = []
    for n in ast.walk(func_node):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "add_parser"
            and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)
        ):
            cmd = n.args[0].value
            out.append(
                CodeUnit(
                    id=CodeUnit.make_id(file_path, f"cli:{cmd}", CodeUnitKind.CLI_COMMAND),
                    kind=CodeUnitKind.CLI_COMMAND, name=cmd, qualified_name=f"cli:{cmd}",
                    signature=(ast.get_source_segment(source, n) or "").strip(),
                    file=file_path, start_line=n.lineno, end_line=getattr(n, "end_lineno", n.lineno),
                    source=ast.get_source_segment(source, n) or "", symbols=[cmd],
                )
            )
    return out


def parse_python_file(path: str | Path, root: str | Path) -> list[CodeUnit]:
    root, path = Path(root), Path(path)
    rel = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    return parse_python_source((root / rel).read_text(encoding="utf-8"), rel)
