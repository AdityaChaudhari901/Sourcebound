"""Second-stage reranking with a cross-encoder.

Two-stage retrieve-then-rerank:
1. Retrieve a wide candidate set (top-N) cheaply with the hybrid bi-encoder/BM25
   retriever — fast, scales to the whole corpus, but coarse ordering.
2. Rerank those N candidates with a **cross-encoder** that reads the query and each
   chunk *together*, producing a much more accurate relevance score, and keep the
   top-k for the LLM.

Why two stages: a cross-encoder is far more accurate but can't be precomputed
(it must run per query-document pair), so it's too expensive to run over the whole
corpus. Running it only over N candidates buys cross-encoder accuracy at
bi-encoder scale. Cost/accuracy knob: larger N = better recall into the reranker
but more cross-encoder compute (latency); smaller k = tighter, less-noisy context
for the LLM. Tune N and k against an eval set.
"""

from __future__ import annotations

import dataclasses
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import settings
from app.rag.retrievers import RetrievedChunk


@runtime_checkable
class Reranker(Protocol):
    def rerank(
        self, query: str, chunks: list[RetrievedChunk], *, top_k: int
    ) -> list[RetrievedChunk]: ...


class CrossEncoderReranker:
    """BGE cross-encoder reranker via fastembed (ONNX, CPU)."""

    def __init__(self, model_name: str) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model_name = model_name
        self._encoder = TextCrossEncoder(model_name=model_name)

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], *, top_k: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = list(self._encoder.rerank(query, [c.text for c in chunks]))
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [
            dataclasses.replace(chunk, score=float(score))
            for chunk, score in ranked[:top_k]
        ]


class NoOpReranker:
    """Disabled reranking: keep the retriever's order, just truncate to top-k."""

    model_name = "none"

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], *, top_k: int
    ) -> list[RetrievedChunk]:
        return chunks[:top_k]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    if not settings.rerank_enabled:
        return NoOpReranker()
    return CrossEncoderReranker(settings.reranker_model)
