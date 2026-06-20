"""The compiled query graph (corrective RAG, taking shape).

    START -> retrieve -> grade_documents -> (relevant?) ┬─ yes -> generate -> END
                                                        └─ no  -> corrective -> END

`grade_documents` filters out irrelevant retrieved docs; a conditional edge then
routes to generation when relevant context survives, or to the corrective path
(a stub for now) when it doesn't. New behavior slots in as nodes + edges without
touching the /query endpoint.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graphs.nodes import (
    corrective,
    decide_to_generate,
    generate,
    grade_documents,
    retrieve,
)
from app.graphs.state import QueryState


def build_query_graph() -> CompiledStateGraph:
    builder = StateGraph(QueryState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade_documents", grade_documents)
    builder.add_node("generate", generate)
    builder.add_node("corrective", corrective)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    # Conditional edge: the router reads state and returns the next node's name.
    builder.add_conditional_edges(
        "grade_documents", decide_to_generate, ["generate", "corrective"]
    )
    builder.add_edge("generate", END)
    builder.add_edge("corrective", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_query_graph() -> CompiledStateGraph:
    """Return the compiled graph (built once)."""
    return build_query_graph()
