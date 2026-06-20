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

from app.core.config import settings
from app.core.logging import get_logger
from app.graphs.state import QueryState
from app.rag.prompting import (
    GRADER_SYSTEM,
    INSUFFICIENT_ANSWER,
    SYSTEM_PROMPT,
    build_grader_prompt,
    build_user_prompt,
)
from app.rag.providers.llm import get_llm_provider
from app.rag.reranking import get_reranker
from app.rag.retrievers import get_retriever

logger = get_logger(__name__)


def retrieve(state: QueryState, config: RunnableConfig) -> dict:
    question = state["question"]
    top_k = (config.get("configurable") or {}).get("k") or settings.query_top_k
    candidates = get_retriever().retrieve(question, k=settings.retrieve_top_n)
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

    logger.info("graph_grade", graded=len(documents), relevant=len(kept))
    return {"documents": kept, "documents_relevant": len(kept) > 0}


def decide_to_generate(state: QueryState) -> Literal["generate", "corrective"]:
    """Conditional edge: relevant docs -> generate; otherwise -> corrective path."""
    return "generate" if state["documents_relevant"] else "corrective"


def corrective(state: QueryState, config: RunnableConfig) -> dict:
    """Stub corrective path: no relevant context, so degrade gracefully for now.

    This is the hook for the real corrective loop (rewrite_query -> re-retrieve,
    or web-search fallback, bounded by `retries`). For now it returns the honest
    insufficiency answer instead of generating from irrelevant context.
    """
    logger.info("graph_corrective_stub", question_len=len(state["question"]))
    return {"documents": [], "generation": INSUFFICIENT_ANSWER}


def generate(state: QueryState, config: RunnableConfig) -> dict:
    documents = state["documents"]
    if not documents:
        return {"generation": INSUFFICIENT_ANSWER}
    answer = get_llm_provider().complete(
        system=SYSTEM_PROMPT,
        user=build_user_prompt(state["question"], documents),
    )
    return {"generation": answer}
