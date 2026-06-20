"""Graph nodes. Each node takes the state, does one step, and returns a partial
state update (never mutates state in place).

- retrieve: hybrid retrieve (top-N) -> cross-encoder rerank (top-k) -> documents.
- generate: ground the cited-answer prompt on the documents and call the LLM.

Per-request `k` arrives via the RunnableConfig (configurable), keeping it out of
the persisted state.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from app.core.config import settings
from app.core.logging import get_logger
from app.graphs.state import QueryState
from app.rag.prompting import INSUFFICIENT_ANSWER, SYSTEM_PROMPT, build_user_prompt
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


def generate(state: QueryState, config: RunnableConfig) -> dict:
    documents = state["documents"]
    if not documents:
        return {"generation": INSUFFICIENT_ANSWER}
    answer = get_llm_provider().complete(
        system=SYSTEM_PROMPT,
        user=build_user_prompt(state["question"], documents),
    )
    return {"generation": answer}
