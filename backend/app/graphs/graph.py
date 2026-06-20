"""The compiled query graph.

Linear for now: START -> retrieve -> generate -> END. This is deliberately the
simplest possible graph — the point is to establish the StateGraph seam so the
corrective-RAG control flow (grade -> conditional rewrite/re-retrieve loop ->
verify) drops in as new nodes and conditional edges without touching the endpoint.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graphs.nodes import generate, retrieve
from app.graphs.state import QueryState


def build_query_graph() -> CompiledStateGraph:
    builder = StateGraph(QueryState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("generate", generate)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_query_graph() -> CompiledStateGraph:
    """Return the compiled graph (built once)."""
    return build_query_graph()
