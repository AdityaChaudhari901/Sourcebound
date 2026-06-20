"""Naive RAG query service: retrieve -> ground -> generate -> cite (synchronous).

Blocking by design (sync embedder, Qdrant, and LLM clients); the route runs it
in a worker thread. When retrieval returns nothing, we short-circuit with the
insufficiency answer and no citations — no point asking the LLM with empty
context. When the model emits the insufficiency sentinel, citations are dropped
so we never present sources for a non-answer.
"""

from __future__ import annotations

from collections.abc import Iterator
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


# --- Streaming event types (yielded by stream_answer) ---


@dataclass(frozen=True)
class TokenChunk:
    text: str


@dataclass(frozen=True)
class FinalResult:
    answer: str
    citations: list[Citation]


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET_CHARS else text[:_SNIPPET_CHARS].rstrip() + "…"


def _retrieve_and_rank(question: str, top_k: int):
    """Stage 1 (hybrid, top-N) -> stage 2 (cross-encoder rerank, top-k)."""
    candidates = get_retriever().retrieve(question, k=settings.retrieve_top_n)
    return candidates, get_reranker().rerank(question, candidates, top_k=top_k)


def _citations_for(answer: str, chunks) -> list[Citation]:
    """Citations for the answer — dropped when the model declared insufficiency."""
    if INSUFFICIENT_ANSWER.lower() in answer.lower():
        return []
    return [
        Citation(source_uri=c.source_uri, chunk_id=c.chunk_id, snippet=_snippet(c.text))
        for c in chunks
    ]


def answer_question(question: str, *, k: int | None = None) -> QueryResult:
    """Non-streaming: retrieve -> rerank -> generate -> cite, returned as one object."""
    candidates, chunks = _retrieve_and_rank(question, k or settings.query_top_k)
    if not chunks:
        logger.info("query_no_context", question_len=len(question))
        return QueryResult(answer=INSUFFICIENT_ANSWER, citations=[])

    provider = get_llm_provider()
    answer = provider.complete(system=SYSTEM_PROMPT, user=build_user_prompt(question, chunks))
    citations = _citations_for(answer, chunks)

    logger.info(
        "query_answered",
        candidates=len(candidates),
        reranked=len(chunks),
        cited=len(citations),
        model=provider.model_name,
    )
    return QueryResult(answer=answer, citations=citations)


def stream_answer(
    question: str, *, k: int | None = None
) -> Iterator[TokenChunk | FinalResult]:
    """Streaming: yield answer tokens as they generate, then a final citations event.

    Same retrieve -> rerank -> ground pipeline as answer_question; only generation
    differs. Citations are emitted at the end because they're dropped when the model
    declares the context insufficient (only known once the full answer is in).
    """
    candidates, chunks = _retrieve_and_rank(question, k or settings.query_top_k)
    if not chunks:
        logger.info("query_no_context", question_len=len(question))
        yield FinalResult(answer=INSUFFICIENT_ANSWER, citations=[])
        return

    provider = get_llm_provider()
    parts: list[str] = []
    for token in provider.stream(system=SYSTEM_PROMPT, user=build_user_prompt(question, chunks)):
        parts.append(token)
        yield TokenChunk(text=token)

    answer = "".join(parts).strip()
    citations = _citations_for(answer, chunks)
    logger.info(
        "query_answered_stream",
        candidates=len(candidates),
        reranked=len(chunks),
        cited=len(citations),
        model=provider.model_name,
    )
    yield FinalResult(answer=answer, citations=citations)
