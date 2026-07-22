"""Local file-backed vector store + content-hash embedding cache.

Default backend — no external service. `DOCGUARD_VECTOR_BACKEND=chroma` can swap
in ChromaDB later behind the same tiny surface (see docs/DECISIONS.md D1).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from docguard.providers.base import EmbeddingProvider


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class CachedEmbedder:
    """Wraps a provider, memoizing by content hash. Persists incrementally."""

    def __init__(self, provider: EmbeddingProvider, cache_path: str | Path | None = None):
        self._p = provider
        self._cache: dict[str, list[float]] = {}
        self._path = Path(cache_path) if cache_path else None
        if self._path and self._path.exists():
            self._cache = json.loads(self._path.read_text(encoding="utf-8"))

    def embed_one(self, text: str) -> list[float]:
        key = f"{self._p.name}:{content_hash(text)}"
        if key not in self._cache:
            self._cache[key] = self._p.embed([text])[0]
            self._flush()
        return self._cache[key]

    def _flush(self) -> None:
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._cache), encoding="utf-8")


class LocalVectorStore:
    def __init__(self) -> None:
        self._items: list[tuple[str, list[float]]] = []

    def add(self, id_: str, vector: list[float]) -> None:
        self._items.append((id_, vector))

    def query(self, vector: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        scored = [(i, cosine(vector, v)) for i, v in self._items]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]
