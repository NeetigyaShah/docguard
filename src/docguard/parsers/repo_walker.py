"""Discover source and documentation files under a repo root."""

from __future__ import annotations

from pathlib import Path

from docguard.parsers.code import CODE_EXTENSIONS

_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".pytest_cache", ".ruff_cache", ".mypy_cache",
}


def _iter_files(root: Path, subdirs: list[str], exts: set[str]) -> list[str]:
    out: list[str] = []
    for sub in subdirs:
        base = root / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_dir():
                continue
            if any(part in _SKIP_DIRS or part.startswith(".docguard") for part in p.parts):
                continue
            if p.suffix in exts:
                out.append(p.relative_to(root).as_posix())
    return sorted(set(out))


# Neetigya, 2026-07-23: `find_code` now uses CODE_EXTENSIONS (py/ts/js/java) instead
# of a hard-coded {".py"}; `find_docs` gained ".mdx" for MDX doc sites (e.g. likec4).
def find_code(root: str | Path, src_paths: list[str] | None = None) -> list[str]:
    root = Path(root)
    return _iter_files(root, src_paths or ["src"], CODE_EXTENSIONS)


def find_docs(root: str | Path, docs_paths: list[str] | None = None) -> list[str]:
    root = Path(root)
    return _iter_files(root, docs_paths or ["docs"], {".md", ".markdown", ".mdx"})
