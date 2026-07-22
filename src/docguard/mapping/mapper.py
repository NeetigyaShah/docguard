"""Code-to-documentation mapping.

Three signals, cheapest first (cost control): exact symbol reference, lexical
overlap, then embedding similarity. Links below the configured threshold are
dropped so unrelated sections are not falsely linked.
"""

from __future__ import annotations

from pathlib import Path

from docguard.mapping.vector_store import CachedEmbedder
from docguard.models import CodeUnit, DocLink, DocSection, MapMethod
from docguard.providers.base import EmbeddingProvider


def _lexical(unit: CodeUnit, section: DocSection) -> float:
    a = {s.lower() for s in unit.symbols}
    b = {s.lower() for s in section.referenced_symbols}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _exact(unit: CodeUnit, section: DocSection) -> bool:
    refs = set(section.referenced_symbols)
    leaf = unit.qualified_name.split(".")[-1].split(":")[-1]
    return bool({unit.name, unit.qualified_name, leaf} & refs)


def _unit_text(u: CodeUnit) -> str:
    return f"{u.qualified_name} {u.signature} {u.docstring} {' '.join(u.symbols)}"


def _section_text(s: DocSection) -> str:
    return f"{' '.join(s.heading_path)} {s.content}"


def build_links(
    units: list[CodeUnit],
    sections: list[DocSection],
    embedder: EmbeddingProvider,
    threshold: float = 0.35,
    cache_path: str | Path | None = None,
) -> list[DocLink]:
    cached = CachedEmbedder(embedder, cache_path)
    unit_vecs = {u.id: cached.embed_one(_unit_text(u)) for u in units}
    sec_vecs = {s.id: cached.embed_one(_section_text(s)) for s in sections}
    from docguard.mapping.vector_store import cosine

    best: dict[tuple[str, str], DocLink] = {}
    for u in units:
        for s in sections:
            key = (u.id, s.id)
            if _exact(u, s):
                best[key] = DocLink(code_unit_id=u.id, doc_section_id=s.id, score=1.0,
                                    method=MapMethod.EXACT)
                continue
            lex = _lexical(u, s)
            emb = cosine(unit_vecs[u.id], sec_vecs[s.id])
            if emb >= lex and emb >= threshold:
                best[key] = DocLink(code_unit_id=u.id, doc_section_id=s.id, score=round(emb, 4),
                                    method=MapMethod.EMBEDDING)
            elif lex >= threshold:
                best[key] = DocLink(code_unit_id=u.id, doc_section_id=s.id, score=round(lex, 4),
                                    method=MapMethod.LEXICAL)

    return sorted(best.values(), key=lambda link: link.score, reverse=True)


def sections_for_unit(unit_id: str, links: list[DocLink]) -> list[str]:
    return [link.doc_section_id for link in links if link.code_unit_id == unit_id]
