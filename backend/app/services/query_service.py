"""Query service — runs the compiled corrective-RAG graph (non-streaming and
streaming) and shapes the result.

Both paths go through the SAME graph (retrieve -> grade -> rewrite/web -> generate
-> verify), so they share the corrective behavior and the metadata the UI shows
(grounding from the verify node, self-correction, web fallback). Streaming uses the
graph's custom stream channel: the generate node emits tokens as it produces them.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.graphs.graph import get_query_graph
from app.rag.prompting import INSUFFICIENT_ANSWER

logger = get_logger(__name__)

_SNIPPET_CHARS = 240


@dataclass(frozen=True)
class Citation:
    source_uri: str
    chunk_id: str
    snippet: str
    external: bool = False  # True = web source (source_uri is a URL), not an internal doc


@dataclass(frozen=True)
class QueryResult:
    answer: str
    citations: list[Citation]
    grounding: float | None = None
    self_corrected: bool = False
    used_web_search: bool = False


# --- Streaming event types (yielded by stream_answer) ---


@dataclass(frozen=True)
class TokenChunk:
    text: str


@dataclass(frozen=True)
class FinalResult:
    answer: str
    citations: list[Citation]
    grounding: float | None = None
    self_corrected: bool = False
    used_web_search: bool = False


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET_CHARS else text[:_SNIPPET_CHARS].rstrip() + "…"


def _citations_for(answer: str, chunks) -> list[Citation]:
    """Citations for the answer — dropped when the model declared insufficiency."""
    if INSUFFICIENT_ANSWER.lower() in answer.lower():
        return []
    return [
        Citation(
            source_uri=c.source_uri,
            chunk_id=c.chunk_id,
            snippet=_snippet(c.text),
            external=c.external,
        )
        for c in chunks
    ]


def _initial_state(question: str) -> dict:
    return {
        "question": question,
        "documents": [],
        "documents_relevant": False,
        "web_search_used": False,
        "generation": "",
        "grounding": None,
        "retries": 0,
    }


def _graph_config(tenant_id: str, k: int | None, history: list[dict] | None) -> dict:
    return {
        "configurable": {
            "k": k or settings.query_top_k,
            "tenant_id": tenant_id,
            "history": history,
        }
    }


def answer_question(
    question: str, *, tenant_id: str, k: int | None = None, history: list[dict] | None = None
) -> QueryResult:
    """Non-streaming: invoke the corrective graph, then shape the result."""
    final = get_query_graph().invoke(
        _initial_state(question), config=_graph_config(tenant_id, k, history)
    )
    documents = final["documents"]
    answer = final["generation"]
    citations = _citations_for(answer, documents) if documents else []
    logger.info(
        "query_answered",
        reranked=len(documents),
        cited=len(citations),
        grounding=final.get("grounding"),
        self_corrected=final["retries"] > 0,
        used_web=final.get("web_search_used", False),
    )
    return QueryResult(
        answer=answer,
        citations=citations,
        grounding=final.get("grounding"),
        self_corrected=final["retries"] > 0,
        used_web_search=final.get("web_search_used", False),
    )


def stream_answer(
    question: str,
    *,
    tenant_id: str,
    k: int | None = None,
    history: list[dict] | None = None,
) -> Iterator[TokenChunk | FinalResult]:
    """Streaming: stream the graph; emit generate-node tokens, then a final event
    with citations + the corrective metadata read from the graph's final state."""
    final_state: dict = {}
    for mode, chunk in get_query_graph().stream(
        _initial_state(question),
        config=_graph_config(tenant_id, k, history),
        stream_mode=["custom", "values"],
    ):
        if mode == "custom":
            token = chunk.get("token")
            if token:
                yield TokenChunk(text=token)
        elif mode == "values":
            final_state = chunk

    documents = final_state.get("documents", [])
    answer = final_state.get("generation", INSUFFICIENT_ANSWER)
    citations = _citations_for(answer, documents) if documents else []
    logger.info(
        "query_answered_stream",
        reranked=len(documents),
        cited=len(citations),
        grounding=final_state.get("grounding"),
    )
    yield FinalResult(
        answer=answer,
        citations=citations,
        grounding=final_state.get("grounding"),
        self_corrected=final_state.get("retries", 0) > 0,
        used_web_search=final_state.get("web_search_used", False),
    )
