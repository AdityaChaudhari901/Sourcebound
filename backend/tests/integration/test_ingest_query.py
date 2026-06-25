"""End-to-end integration tests over real Postgres + Qdrant.

Covers ingest -> retrieve -> answer and the tenant-isolation invariant: a query
can never read another tenant's vectors. The LLM is mocked (grade/generate/verify)
so the test is deterministic; embeddings, vector store, and DB are real.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class _GraphLLM:
    """Routes by the system prompt so one fake serves grade, verify, and generate."""

    model_name = "fake"

    def __init__(self, *, keep: str = "[1, 2, 3, 4, 5]", grounding: str = "0.95") -> None:
        self._keep = keep
        self._grounding = grounding

    def complete(self, *, system: str, user: str) -> str:
        s = system.lower()
        if "relevance grader" in s:
            return self._keep
        if "grounding verifier" in s:
            return self._grounding
        return ""

    def stream(self, *, system: str, user: str):
        yield "Rotate the payments secret every 90 days [1]."


def test_ingest_indexed_chunks(seeded):
    assert seeded.chunk_count >= 1


def test_tenant_retrieves_its_own_chunks(seeded):
    from app.rag.retrievers import get_retriever

    hits = get_retriever().retrieve(
        "how often should I rotate the payments secret", k=5, tenant_id=str(seeded.a)
    )
    assert hits, "tenant A should retrieve its own ingested chunks"
    assert any("rotate" in h.text.lower() or "payments" in h.text.lower() for h in hits)
    assert all(h.document_id for h in hits)  # citation provenance carried through


def test_tenant_isolation_other_tenant_sees_nothing(seeded):
    from app.rag.retrievers import get_retriever

    hits = get_retriever().retrieve(
        "how often should I rotate the payments secret", k=5, tenant_id=str(seeded.b)
    )
    assert hits == [], "tenant B must not see tenant A's vectors"


def test_end_to_end_query_returns_cited_grounded_answer(seeded, monkeypatch):
    import app.graphs.nodes as nodes
    from app.services.query_service import answer_question

    monkeypatch.setattr(nodes, "get_llm_provider", lambda: _GraphLLM())

    result = answer_question(
        "how often should I rotate the payments secret", tenant_id=str(seeded.a), k=3
    )
    assert result.answer.strip()
    assert result.citations, "a grounded answer must carry citations"
    assert result.grounding == 0.95
    assert any(c.source_uri == "runbook.md" for c in result.citations)


def test_end_to_end_other_tenant_degrades_to_insufficient(seeded, monkeypatch):
    import app.graphs.nodes as nodes
    from app.rag.prompting import INSUFFICIENT_ANSWER
    from app.services.query_service import answer_question

    monkeypatch.setattr(nodes, "get_llm_provider", lambda: _GraphLLM())

    result = answer_question(
        "how often should I rotate the payments secret", tenant_id=str(seeded.b), k=3
    )
    assert INSUFFICIENT_ANSWER in result.answer
    assert result.citations == []  # no sources for a non-answer
