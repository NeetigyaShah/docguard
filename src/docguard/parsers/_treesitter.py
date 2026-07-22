"""Thin tree-sitter helpers shared by the non-Python language parsers.

One grammar API for every language via `tree-sitter-language-pack` (prebuilt
wheels, no compiler needed). Kept tiny on purpose — the per-language extraction
logic lives in `code_<lang>.py`; this module only loads a grammar and reads node
text. Import is lazy at call time so the core never hard-requires the grammars.
"""

from __future__ import annotations

from typing import Any


def parse_tree(source: str, lang: str) -> Any:
    """Parse `source` with the named grammar (e.g. 'typescript', 'java')."""
    from tree_sitter_language_pack import get_parser

    return get_parser(lang).parse(bytes(source, "utf-8"))


def node_text(node: Any, src: bytes) -> str:
    """Exact source slice for a node (bytes → str, lossless on valid UTF-8)."""
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def first_child(node: Any, *types: str) -> Any | None:
    for c in node.children:
        if c.type in types:
            return c
    return None


def walk(node: Any):
    """Depth-first iterator over every node in the tree."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))
