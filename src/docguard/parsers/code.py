# Neetigya, 2026-07-23: new file — the universal parser router that made DocGuard
# multi-language. Dispatches each source file to its per-language parser by extension.
"""Language-agnostic code parser: dispatch a source file to its parser.

Every pipeline stage that used to call `parse_python_source` now calls
`parse_code_source` here, so DocGuard heals docs for polyglot repos (the common
case in a corporate monorepo: TS/JS frontend, Java backend, Python services)
through the exact same detect→map→verify→repair flow.

Contract for a language module: expose `parse_source(source, path) -> list[CodeUnit]`.
The Python parser keeps its historical `parse_python_source` name; the rest use
`parse_source`. Missing grammar or a single malformed file degrades to `[]` —
never a crash — so one bad file cannot break a CI run.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from docguard.models import CodeUnit

# extension (no dot) -> (module, function name)
_DISPATCH: dict[str, tuple[str, str]] = {
    "py": ("docguard.parsers.code_python", "parse_python_source"),
    "ts": ("docguard.parsers.code_typescript", "parse_source"),
    "tsx": ("docguard.parsers.code_typescript", "parse_source"),
    "js": ("docguard.parsers.code_javascript", "parse_source"),
    "jsx": ("docguard.parsers.code_javascript", "parse_source"),
    "mjs": ("docguard.parsers.code_javascript", "parse_source"),
    "cjs": ("docguard.parsers.code_javascript", "parse_source"),
    "java": ("docguard.parsers.code_java", "parse_source"),
}

CODE_EXTENSIONS: set[str] = {"." + e for e in _DISPATCH}


def _ext(path: str) -> str:
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def parse_code_source(source: str, path: str) -> list[CodeUnit]:
    # A UTF-8 BOM (common on Windows-authored files, and preserved by `git show`)
    # makes `ast.parse` raise and silently yields zero code units — i.e. DocGuard
    # would report "no changes" on every file. Strip it at the single entry point
    # every source string flows through (disk reads *and* git revisions).
    source = source.lstrip("﻿")
    target = _DISPATCH.get(_ext(path))
    if not target:
        return []
    mod_name, fn_name = target
    try:
        fn = getattr(importlib.import_module(mod_name), fn_name)
    except Exception:  # language module or its grammar unavailable
        return []
    try:
        return fn(source, path)
    except Exception:  # CI safety: one bad file never crashes the run
        return []


def parse_code_file(path: str | Path, root: str | Path) -> list[CodeUnit]:
    root, path = Path(root), Path(path)
    rel = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    return parse_code_source((root / rel).read_text(encoding="utf-8"), rel)
