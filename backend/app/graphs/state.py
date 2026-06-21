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
    documents_relevant: bool  # grade: did any retrieved doc survive relevance grading?
    web_search_used: bool     # did the web-fallback path fire?
    generation: str
    grounding: float | None   # verify node: 0-1 how grounded the answer is (None if N/A)
    retries: int              # >0 means the query was self-corrected (rewrite loop)
