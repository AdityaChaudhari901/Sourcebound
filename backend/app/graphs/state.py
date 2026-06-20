"""Shared state for the query graph.

State is the graph's working memory — every node reads from it and returns a
partial update that LangGraph merges in. Kept minimal for now; `retries` is
unused by the linear flow but is the hook for the corrective loop coming next
(grade docs -> rewrite query -> re-retrieve, bounded by retries).
"""

from __future__ import annotations

from typing_extensions import TypedDict

from app.rag.retrievers import RetrievedChunk


class QueryState(TypedDict):
    question: str
    documents: list[RetrievedChunk]
    generation: str
    retries: int
