"""Markdown documentation parser → DocSection list.

Sections are keyed by nested heading path. Each section's content is its own
body (child headings start new sections). Referenced symbols are pulled from
inline `code` spans and fenced code blocks.
"""

from __future__ import annotations

import re
from pathlib import Path

from docguard.models import DocSection

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_FENCE = re.compile(r"^\s*```")


def _symbols(text: str) -> list[str]:
    syms: set[str] = set()
    for span in _INLINE_CODE.findall(text):
        for tok in _IDENT.findall(span):
            syms.add(tok)
            if "." in tok:  # also index the leaf, e.g. UserService.remove_member
                syms.add(tok.split(".")[-1])
    return sorted(syms)


def parse_markdown_source(text: str, doc_path: str) -> list[DocSection]:
    # strip a UTF-8 BOM so a leading `# Heading` is still recognised (see code.py)
    lines = text.lstrip("﻿").splitlines()
    # locate heading lines (ignoring those inside fenced code blocks)
    headings: list[tuple[int, int, str]] = []  # (line_idx, level, title)
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        if m:
            headings.append((i, len(m.group(1)), m.group(2).strip()))

    sections: list[DocSection] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    for idx, (line_i, level, title) in enumerate(headings):
        while stack and stack[-1][0] >= level:
            stack.pop()
        heading_path = [t for _, t in stack] + [title]
        stack.append((level, title))

        body_start = line_i + 1
        body_end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        content = "\n".join(lines[body_start:body_end]).strip("\n")

        sections.append(
            DocSection(
                id=DocSection.make_id(doc_path, heading_path),
                doc_path=doc_path, heading=title, heading_path=heading_path, level=level,
                content=content, start_line=line_i + 1, end_line=body_end,
                referenced_symbols=_symbols(title + "\n" + content),
            )
        )
    return sections


def parse_markdown_file(path: str | Path, root: str | Path) -> list[DocSection]:
    root, path = Path(root), Path(path)
    rel = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    return parse_markdown_source((root / rel).read_text(encoding="utf-8"), rel)
