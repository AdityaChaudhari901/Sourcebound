"""Retriever interface and dense / sparse / hybrid implementations.

The query endpoint depends only on the ``Retriever`` protocol and ``get_retriever()``
— it never knows whether retrieval is dense, sparse, or fused.

- **Dense** (BGE cosine) matches *meaning* — "how do I sign in" finds "authentication".
- **Sparse** (BM25 lexical) matches *exact tokens* — service names, env vars, error
  codes, function names that dense embeddings blur together.
- **Hybrid** fuses both ranked lists with weighted Reciprocal Rank Fusion (RRF), so
  an internal tech KB (full of both prose questions and exact identifiers) gets the
  recall of both. Weights and depth are configurable.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from qdrant_client import models

from app.core.config import settings
from app.rag.providers.embeddings import (
    get_embedding_provider,
    get_sparse_embedding_provider,
)
from app.vectorstore.qdrant import DENSE_VECTOR, SPARSE_VECTOR, get_qdrant_client


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    source_uri: str
    heading_path: str | None
    text: str
    score: float  # cosine/BM25 for single retrievers; fused RRF score for hybrid
    external: bool = False  # True for web-search results (source_uri is a URL)


@runtime_checkable
class Retriever(Protocol):
    def retrieve(self, query: str, *, k: int) -> list[RetrievedChunk]: ...


def _point_to_chunk(point) -> RetrievedChunk:
    payload = point.payload or {}
    return RetrievedChunk(
        chunk_id=payload.get("chunk_id", str(point.id)),
        document_id=payload.get("document_id", ""),
        source_uri=payload.get("source_uri", "unknown"),
        heading_path=payload.get("heading_path"),
        text=payload.get("text", ""),
        score=point.score,
    )


class DenseRetriever:
    """Semantic retrieval over BGE embeddings."""

    def retrieve(self, query: str, *, k: int) -> list[RetrievedChunk]:
        vector = get_embedding_provider().embed_query(query)
        response = get_qdrant_client().query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            using=DENSE_VECTOR,
            limit=k,
            with_payload=True,
        )
        return [_point_to_chunk(p) for p in response.points]


class SparseRetriever:
    """Lexical retrieval over BM25 sparse vectors."""

    def retrieve(self, query: str, *, k: int) -> list[RetrievedChunk]:
        sparse = get_sparse_embedding_provider().embed_query(query)
        response = get_qdrant_client().query_points(
            collection_name=settings.qdrant_collection,
            query=models.SparseVector(indices=sparse.indices, values=sparse.values),
            using=SPARSE_VECTOR,
            limit=k,
            with_payload=True,
        )
        return [_point_to_chunk(p) for p in response.points]


def reciprocal_rank_fusion(
    ranked_lists: list[tuple[list[RetrievedChunk], float]],
    *,
    rrf_k: int,
    k: int,
) -> list[RetrievedChunk]:
    """Weighted RRF: score(doc) = Σ_list weight / (rrf_k + rank). Higher = better."""
    fused: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}
    for results, weight in ranked_lists:
        for rank, chunk in enumerate(results):
            key = chunk.chunk_id
            fused[key] = fused.get(key, 0.0) + weight / (rrf_k + rank + 1)
            chunks.setdefault(key, chunk)
    ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:k]
    return [dataclasses.replace(chunks[key], score=score) for key, score in ordered]


class HybridRetriever:
    def __init__(
        self,
        dense: Retriever,
        sparse: Retriever,
        *,
        dense_weight: float,
        sparse_weight: float,
        rrf_k: int,
        prefetch: int,
    ) -> None:
        self._dense = dense
        self._sparse = sparse
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._rrf_k = rrf_k
        self._prefetch = prefetch

    def retrieve(self, query: str, *, k: int) -> list[RetrievedChunk]:
        depth = max(k, self._prefetch)
        dense_hits = self._dense.retrieve(query, k=depth)
        sparse_hits = self._sparse.retrieve(query, k=depth)
        return reciprocal_rank_fusion(
            [(dense_hits, self._dense_weight), (sparse_hits, self._sparse_weight)],
            rrf_k=self._rrf_k,
            k=k,
        )


def get_retriever() -> Retriever:
    """Build the retriever from settings.retriever_mode (hybrid | dense | sparse)."""
    mode = settings.retriever_mode.lower()
    if mode == "dense":
        return DenseRetriever()
    if mode == "sparse":
        return SparseRetriever()
    return HybridRetriever(
        DenseRetriever(),
        SparseRetriever(),
        dense_weight=settings.hybrid_dense_weight,
        sparse_weight=settings.hybrid_sparse_weight,
        rrf_k=settings.hybrid_rrf_k,
        prefetch=settings.hybrid_prefetch_limit,
    )
