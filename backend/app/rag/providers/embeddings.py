"""Embedding provider interface and the default open-model (BGE) implementation.

Services depend on the ``EmbeddingProvider`` protocol, never on a concrete SDK,
so swapping BGE for another local model or a hosted API is a config change.

Default: FastEmbed with ``BAAI/bge-small-en-v1.5`` (384-dim, ONNX) — open,
self-hosted, no torch, data never leaves the box. BGE distinguishes *document*
and *query* embeddings (the query form adds an instruction prefix), so the two
methods are kept separate and must use the same model.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import settings


@runtime_checkable
class EmbeddingProvider(Protocol):
    model_name: str

    @property
    def dimension(self) -> int:
        """Vector dimension — must match the Qdrant collection's vector size."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed chunk texts for indexing."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (may differ from document embedding for BGE)."""
        ...


class FastEmbedProvider:
    """EmbeddingProvider backed by fastembed (ONNX, CPU)."""

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(next(iter(self._model.embed(["probe"]))))
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider (cached; loads the model once)."""
    if settings.embedding_provider == "fastembed":
        return FastEmbedProvider(settings.embedding_model)
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider!r}")


# --- Sparse (BM25) embeddings for lexical retrieval --------------------------------


@dataclass(frozen=True)
class SparseVectorData:
    """Provider-agnostic sparse vector (term index -> weight)."""

    indices: list[int]
    values: list[float]


@runtime_checkable
class SparseEmbeddingProvider(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[SparseVectorData]: ...

    def embed_query(self, text: str) -> SparseVectorData: ...


class FastEmbedSparseProvider:
    """BM25 sparse embeddings via fastembed (term frequencies; IDF applied in Qdrant)."""

    def __init__(self, model_name: str) -> None:
        from fastembed import SparseTextEmbedding

        self.model_name = model_name
        self._model = SparseTextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[SparseVectorData]:
        return [
            SparseVectorData(indices=e.indices.tolist(), values=e.values.tolist())
            for e in self._model.embed(texts)
        ]

    def embed_query(self, text: str) -> SparseVectorData:
        e = next(iter(self._model.query_embed(text)))
        return SparseVectorData(indices=e.indices.tolist(), values=e.values.tolist())


@lru_cache(maxsize=1)
def get_sparse_embedding_provider() -> SparseEmbeddingProvider:
    return FastEmbedSparseProvider(settings.sparse_embedding_model)
