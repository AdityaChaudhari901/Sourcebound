"""The compiled query graph (corrective RAG with a bounded rewrite loop).

    START -> retrieve -> grade_documents -> (relevant?)
        ├─ relevant ............................-> generate -> END
        ├─ not relevant & retries < cap ........-> rewrite_query -> retrieve  (loop)
        └─ not relevant & retries >= cap .......-> generate -> END  (graceful degrade)

The loop (retrieve -> grade -> rewrite -> retrieve) is what makes this a *graph*,
not a chain. `retries` (capped by settings.max_query_retries) guarantees it
terminates: after the cap we stop rewriting and generate from the best-available
context instead of looping forever.
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
)
from app.graphs.state import QueryState


def build_query_graph() -> CompiledStateGraph:
    builder = StateGraph(QueryState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade_documents", grade_documents)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("generate", generate)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    # Conditional edge: router reads state (relevance + retries) and picks the next node.
    builder.add_conditional_edges(
        "grade_documents", decide_after_grade, ["generate", "rewrite_query"]
    )
    builder.add_edge("rewrite_query", "retrieve")  # the loop back
    builder.add_edge("generate", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_query_graph() -> CompiledStateGraph:
    """Return the compiled graph (built once)."""
    return build_query_graph()
