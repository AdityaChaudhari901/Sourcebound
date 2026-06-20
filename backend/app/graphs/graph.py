"""The compiled query graph (corrective RAG with rewrite loop + web fallback).

    START -> retrieve -> grade_documents -> (relevant?)
        ├─ relevant ............................-> generate -> END
        ├─ not relevant & retries < cap ........-> rewrite_query -> retrieve  (loop)
        ├─ not relevant & at cap & web on ......-> web_search -> generate -> END
        └─ not relevant & at cap & no web ......-> generate -> END  (graceful degrade)

The loop (retrieve -> grade -> rewrite -> retrieve) is what makes this a *graph*,
not a chain. `retries` (capped by settings.max_query_retries) guarantees it
terminates. When the loop is exhausted and web search is configured, web_search is
the external escape hatch; its results flow into the same generate node, cited as
external URLs.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graphs.nodes import (
    decide_after_grade,
    generate,
    grade_documents,
    retrieve,
    rewrite_query,
    web_search,
)
from app.graphs.state import QueryState


def build_query_graph() -> CompiledStateGraph:
    builder = StateGraph(QueryState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade_documents", grade_documents)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("web_search", web_search)
    builder.add_node("generate", generate)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    # Conditional edge: router reads state (relevance + retries + web config).
    builder.add_conditional_edges(
        "grade_documents",
        decide_after_grade,
        ["generate", "rewrite_query", "web_search"],
    )
    builder.add_edge("rewrite_query", "retrieve")  # the loop back
    builder.add_edge("web_search", "generate")  # web results -> grounded generation
    builder.add_edge("generate", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_query_graph() -> CompiledStateGraph:
    """Return the compiled graph (built once)."""
    return build_query_graph()
