"""Naive RAG query service: retrieve -> ground -> generate -> cite (synchronous).

Blocking by design (sync embedder, Qdrant, and LLM clients); the route runs it
in a worker thread. When retrieval returns nothing, we short-circuit with the
insufficiency answer and no citations — no point asking the LLM with empty
context. When the model emits the insufficiency sentinel, citations are dropped
so we never present sources for a non-answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.prompting import (
    INSUFFICIENT_ANSWER,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.rag.providers.llm import get_llm_provider
from app.rag.reranking import get_reranker
from app.rag.retrievers import get_retriever

logger = get_logger(__name__)

_SNIPPET_CHARS = 240


@dataclass(frozen=True)
class Citation:
    source_uri: str
    chunk_id: str
    snippet: str


@dataclass(frozen=True)
class QueryResult:
    answer: str
    citations: list[Citation]


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET_CHARS else text[:_SNIPPET_CHARS].rstrip() + "…"


def answer_question(question: str, *, k: int | None = None) -> QueryResult:
    top_k = k or settings.query_top_k
    # Stage 1: retrieve a wide candidate set (N) via hybrid retrieval.
    candidates = get_retriever().retrieve(question, k=settings.retrieve_top_n)
    # Stage 2: rerank the candidates with a cross-encoder down to top-k for the LLM.
    chunks = get_reranker().rerank(question, candidates, top_k=top_k)

    if not chunks:
        logger.info("query_no_context", question_len=len(question))
        return QueryResult(answer=INSUFFICIENT_ANSWER, citations=[])

    provider = get_llm_provider()
    user_prompt = build_user_prompt(question, chunks)
    answer = provider.complete(system=SYSTEM_PROMPT, user=user_prompt)

    # Drop citations when the model declared the context insufficient.
    insufficient = INSUFFICIENT_ANSWER.lower() in answer.lower()
    citations = (
        []
        if insufficient
        else [
            Citation(
                source_uri=chunk.source_uri,
                chunk_id=chunk.chunk_id,
                snippet=_snippet(chunk.text),
            )
            for chunk in chunks
        ]
    )

    logger.info(
        "query_answered",
        candidates=len(candidates),
        reranked=len(chunks),
        cited=len(citations),
        insufficient=insufficient,
        model=provider.model_name,
    )
    return QueryResult(answer=answer, citations=citations)
