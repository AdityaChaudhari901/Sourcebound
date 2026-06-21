"""Graph nodes. Each node takes the state, does one step, and returns a partial
state update (never mutates state in place).

- retrieve: hybrid retrieve (top-N) -> cross-encoder rerank (top-k) -> documents.
- generate: ground the cited-answer prompt on the documents and call the LLM.

Per-request `k` arrives via the RunnableConfig (configurable), keeping it out of
the persisted state.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from app.core.config import settings
from app.core.logging import get_logger
from app.graphs.state import QueryState
from app.rag.prompting import (
    GRADER_SYSTEM,
    INSUFFICIENT_ANSWER,
    REWRITE_SYSTEM,
    SYSTEM_PROMPT,
    VERIFY_SYSTEM,
    build_grader_prompt,
    build_rewrite_prompt,
    build_user_prompt,
    build_verify_prompt,
)
from app.rag.providers.llm import get_llm_provider
from app.rag.providers.search import get_search_provider
from app.rag.reranking import get_reranker
from app.rag.retrievers import RetrievedChunk, get_retriever

logger = get_logger(__name__)


def retrieve(state: QueryState, config: RunnableConfig) -> dict:
    question = state["question"]
    configurable = config.get("configurable") or {}
    top_k = configurable.get("k") or settings.query_top_k
    tenant_id = configurable["tenant_id"]  # required — no tenant, no retrieval
    candidates = get_retriever().retrieve(
        question, k=settings.retrieve_top_n, tenant_id=tenant_id
    )
    documents = get_reranker().rerank(question, candidates, top_k=top_k)
    logger.info("graph_retrieve", candidates=len(candidates), reranked=len(documents))
    return {"documents": documents}


def _parse_relevant_indices(raw: str, count: int) -> list[int] | None:
    """Parse the grader's JSON index list. Returns None on unparseable output."""
    match = re.search(r"\[.*?\]", raw, re.S)
    if not match:
        return None  # no array at all -> treat as parse failure (caller keeps all)
    try:
        values = json.loads(match.group(0))
        indices = [int(v) for v in values]
    except (ValueError, TypeError):
        indices = [int(n) for n in re.findall(r"\d+", match.group(0))]
    return [i for i in indices if 1 <= i <= count]


def grade_documents(state: QueryState, config: RunnableConfig) -> dict:
    """LLM-as-grader: keep only documents relevant to the question.

    One batched call (not one per doc) returns the relevant indices. On a parse
    failure we keep ALL documents (fail-open / lenient) so a flaky grader never
    silently drops a correct answer.
    """
    documents = state["documents"]
    if not documents:
        return {"documents_relevant": False}

    raw = get_llm_provider().complete(
        system=GRADER_SYSTEM,
        user=build_grader_prompt(state["question"], documents),
    )
    indices = _parse_relevant_indices(raw, len(documents))
    if indices is None:
        kept = documents  # parse failure -> fail open
    else:
        kept = [documents[i - 1] for i in indices]

    relevant = len(kept) > 0
    logger.info("graph_grade", graded=len(documents), relevant=len(kept))
    # When relevant, narrow to the clean subset. When NOT relevant, leave the full
    # reranked set in state so the degradation path still has "best-available" docs.
    if relevant:
        return {"documents": kept, "documents_relevant": True}
    return {"documents_relevant": False}


def decide_after_grade(
    state: QueryState,
) -> Literal["generate", "rewrite_query", "web_search"]:
    """Conditional edge after grading:

    - relevant docs ...........................-> generate
    - not relevant, under cap .................-> rewrite_query (loop back to retrieve)
    - not relevant, at cap, web configured ....-> web_search (external fallback)
    - not relevant, at cap, no web ............-> generate (degrade on best-available docs)
    """
    if state["documents_relevant"]:
        return "generate"
    if state["retries"] < settings.max_query_retries:
        return "rewrite_query"
    return "web_search" if settings.web_search_configured else "generate"


def web_search(state: QueryState, config: RunnableConfig) -> dict:
    """Last-resort fallback: search the public web and use the results as context.

    Fires only after the rewrite loop is exhausted and internal context is still
    irrelevant. Results become `documents` marked ``external=True`` (source_uri is a
    URL), so generation cites them and the response distinguishes them from internal
    sources. Flows on to generate, which grounds + cites as usual.
    """
    results = get_search_provider().search(
        state["question"], max_results=settings.web_search_max_results
    )
    documents = [
        RetrievedChunk(
            chunk_id=result.url,
            document_id="web",
            source_uri=result.url,
            heading_path=result.title or None,
            text=result.content,
            score=0.0,
            external=True,
        )
        for result in results
        if result.content
    ]
    logger.info("graph_web_search", results=len(documents))
    return {"documents": documents, "documents_relevant": bool(documents), "web_search_used": True}


def rewrite_query(state: QueryState, config: RunnableConfig) -> dict:
    """Reformulate the question for better retrieval and increment the retry count.

    The rewrite is intent-preserving (a better *search query*), then the graph loops
    back to retrieve with it. `retries` is the loop guard read by decide_after_grade.
    """
    original = state["question"]
    rewritten = get_llm_provider().complete(
        system=REWRITE_SYSTEM, user=build_rewrite_prompt(original)
    ).strip()
    rewritten = rewritten or original
    retries = state["retries"] + 1
    logger.info("graph_rewrite", retries=retries, rewritten=rewritten[:80])
    return {"question": rewritten, "retries": retries}


def _parse_grounding(raw: str) -> float | None:
    match = re.search(r"\d*\.?\d+", raw)
    if not match:
        return None
    return max(0.0, min(1.0, float(match.group(0))))


def generate(state: QueryState, config: RunnableConfig) -> dict:
    documents = state["documents"]
    if not documents:
        return {"generation": INSUFFICIENT_ANSWER}
    history = (config.get("configurable") or {}).get("history")

    # Stream tokens through LangGraph's custom stream channel when the graph is
    # being streamed; a no-op writer when it's invoked, so /query still works.
    try:
        writer = get_stream_writer()
    except Exception:  # noqa: BLE001 - not in a streaming context
        writer = None

    parts: list[str] = []
    for token in get_llm_provider().stream(
        system=SYSTEM_PROMPT, user=build_user_prompt(state["question"], documents, history)
    ):
        parts.append(token)
        if writer is not None:
            writer({"token": token})
    return {"generation": "".join(parts).strip()}


def verify_grounding(state: QueryState, config: RunnableConfig) -> dict:
    """Verify node: rate how grounded the answer is in the retrieved context (0-1)."""
    documents = state["documents"]
    answer = state["generation"]
    if not documents or INSUFFICIENT_ANSWER.lower() in answer.lower():
        return {"grounding": None}
    raw = get_llm_provider().complete(
        system=VERIFY_SYSTEM, user=build_verify_prompt(answer, documents)
    )
    grounding = _parse_grounding(raw)
    logger.info("graph_verify", grounding=grounding)
    return {"grounding": grounding}
