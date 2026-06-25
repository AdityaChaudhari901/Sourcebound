"""Unit tests for each LangGraph node's logic (LLM/retriever/search mocked).

Nodes import their provider getters into the `nodes` module namespace, so we
monkeypatch `nodes.get_*` and the node picks up the fake at call time.
"""

from __future__ import annotations

from pydantic import SecretStr

import app.graphs.nodes as nodes
from app.graphs.nodes import (
    _parse_grounding,
    _parse_relevant_indices,
    decide_after_grade,
    generate,
    grade_documents,
    retrieve,
    rewrite_query,
    verify_grounding,
    web_search,
)
from app.rag.prompting import INSUFFICIENT_ANSWER

from tests.conftest import FakeLLM, FakeReranker, FakeRetriever, FakeSearchProvider, FakeSearchResult


def cfg(**configurable):
    return {"configurable": configurable}


# --- retrieve --------------------------------------------------------------------


def test_retrieve_reranks_candidates_and_passes_tenant(monkeypatch, make_chunk):
    candidates = [make_chunk(c) for c in "abcde"]
    retriever = FakeRetriever(candidates)
    reranker = FakeReranker()  # passthrough + truncate to top_k
    monkeypatch.setattr(nodes, "get_retriever", lambda: retriever)
    monkeypatch.setattr(nodes, "get_reranker", lambda: reranker)

    out = retrieve({"question": "q"}, cfg(k=2, tenant_id="tenant-x"))

    assert [c.chunk_id for c in out["documents"]] == ["a", "b"]  # reranked to k=2
    # retrieval used the wide top-N and the required tenant id
    assert retriever.calls[0][1] == nodes.settings.retrieve_top_n
    assert retriever.calls[0][2] == "tenant-x"
    assert reranker.calls[0][2] == 2  # top_k forwarded from config


# --- grade_documents -------------------------------------------------------------


def test_grade_empty_documents_short_circuits():
    assert grade_documents({"documents": [], "question": "q"}, cfg()) == {
        "documents_relevant": False
    }


def test_grade_keeps_only_relevant_indices(monkeypatch, make_chunk):
    docs = [make_chunk("a"), make_chunk("b"), make_chunk("c")]
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: FakeLLM(complete="[1, 3]"))
    out = grade_documents({"documents": docs, "question": "q"}, cfg())
    assert out["documents_relevant"] is True
    assert [c.chunk_id for c in out["documents"]] == ["a", "c"]


def test_grade_none_relevant_keeps_full_set_but_flags_irrelevant(monkeypatch, make_chunk):
    docs = [make_chunk("a"), make_chunk("b")]
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: FakeLLM(complete="[]"))
    out = grade_documents({"documents": docs, "question": "q"}, cfg())
    assert out == {"documents_relevant": False}  # docs left untouched for degradation path


def test_grade_parse_failure_fails_open(monkeypatch, make_chunk):
    docs = [make_chunk("a"), make_chunk("b")]
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: FakeLLM(complete="totally not json"))
    out = grade_documents({"documents": docs, "question": "q"}, cfg())
    # no parseable array -> keep ALL documents rather than silently dropping a hit
    assert out["documents_relevant"] is True
    assert len(out["documents"]) == 2


def test_parse_relevant_indices_clamps_out_of_range():
    assert _parse_relevant_indices("[1, 2, 9]", 2) == [1, 2]  # 9 dropped
    assert _parse_relevant_indices("no array here", 3) is None
    assert _parse_relevant_indices("[2, 1]", 3) == [2, 1]


def test_parse_relevant_indices_recovers_from_malformed_json():
    # The grader output is LLM-generated; if it isn't valid JSON but digits are
    # present, fall back to extracting them rather than dropping everything.
    assert _parse_relevant_indices("[1, two, 3]", 3) == [1, 3]


# --- decide_after_grade (the corrective router) ----------------------------------


def test_decide_routes_to_generate_when_relevant():
    state = {"documents_relevant": True, "retries": 0}
    assert decide_after_grade(state) == "generate"


def test_decide_routes_to_rewrite_under_retry_cap(monkeypatch):
    monkeypatch.setattr(nodes.settings, "max_query_retries", 2)
    state = {"documents_relevant": False, "retries": 1}
    assert decide_after_grade(state) == "rewrite_query"


def test_decide_degrades_to_generate_at_cap_without_web(monkeypatch):
    monkeypatch.setattr(nodes.settings, "max_query_retries", 2)
    monkeypatch.setattr(nodes.settings, "web_search_enabled", False)
    state = {"documents_relevant": False, "retries": 2}
    assert decide_after_grade(state) == "generate"


def test_decide_uses_web_search_at_cap_when_configured(monkeypatch):
    monkeypatch.setattr(nodes.settings, "max_query_retries", 2)
    monkeypatch.setattr(nodes.settings, "web_search_enabled", True)
    monkeypatch.setattr(nodes.settings, "tavily_api_key", SecretStr("key"))
    state = {"documents_relevant": False, "retries": 2}
    assert decide_after_grade(state) == "web_search"


# --- rewrite_query ---------------------------------------------------------------


def test_rewrite_replaces_question_and_increments_retries(monkeypatch):
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: FakeLLM(complete="  better query  "))
    out = rewrite_query({"question": "orig", "retries": 0}, cfg())
    assert out == {"question": "better query", "retries": 1}


def test_rewrite_falls_back_to_original_on_empty_output(monkeypatch):
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: FakeLLM(complete="   "))
    out = rewrite_query({"question": "orig", "retries": 1}, cfg())
    assert out["question"] == "orig"
    assert out["retries"] == 2


# --- web_search ------------------------------------------------------------------


def test_web_search_maps_results_to_external_chunks(monkeypatch):
    results = [
        FakeSearchResult("https://x.com/a", "Title A", "content a"),
        FakeSearchResult("https://x.com/b", None, ""),  # empty content -> dropped
    ]
    monkeypatch.setattr(nodes, "get_search_provider", lambda: FakeSearchProvider(results))
    out = web_search({"question": "q"}, cfg())
    assert out["web_search_used"] is True
    assert out["documents_relevant"] is True
    assert len(out["documents"]) == 1  # the empty-content result was filtered out
    doc = out["documents"][0]
    assert doc.external is True
    assert doc.source_uri == "https://x.com/a"
    assert doc.heading_path == "Title A"


# --- generate --------------------------------------------------------------------


def test_generate_returns_insufficiency_without_documents():
    assert generate({"documents": [], "question": "q"}, cfg()) == {
        "generation": INSUFFICIENT_ANSWER
    }


def test_generate_joins_streamed_tokens(monkeypatch, make_chunk):
    monkeypatch.setattr(
        nodes, "get_llm_provider", lambda: FakeLLM(tokens=["Rotate ", "every ", "90 days [1]."])
    )
    out = generate({"documents": [make_chunk("a")], "question": "q"}, cfg(history=None))
    assert out["generation"] == "Rotate every 90 days [1]."


# --- verify_grounding ------------------------------------------------------------


def test_verify_returns_none_without_documents():
    assert verify_grounding({"documents": [], "generation": "x"}, cfg()) == {"grounding": None}


def test_verify_returns_none_for_insufficiency_answer(make_chunk):
    state = {"documents": [make_chunk("a")], "generation": INSUFFICIENT_ANSWER}
    assert verify_grounding(state, cfg()) == {"grounding": None}


def test_verify_parses_grounding_score(monkeypatch, make_chunk):
    monkeypatch.setattr(nodes, "get_llm_provider", lambda: FakeLLM(complete="0.95"))
    state = {"documents": [make_chunk("a")], "generation": "An answer [1]."}
    assert verify_grounding(state, cfg()) == {"grounding": 0.95}


def test_parse_grounding_clamps_and_handles_garbage():
    assert _parse_grounding("0.8") == 0.8
    assert _parse_grounding("1.5") == 1.0  # clamped to [0, 1]
    assert _parse_grounding("score: 0") == 0.0
    assert _parse_grounding("no number") is None
