"""Unit tests for the cross-encoder reranker + get_reranker() wiring."""

from __future__ import annotations

import app.rag.reranking as rr


def test_noop_reranker_truncates_and_preserves_order(make_chunk):
    chunks = [make_chunk(c) for c in "abcd"]
    out = rr.NoOpReranker().rerank("q", chunks, top_k=2)
    assert [c.chunk_id for c in out] == ["a", "b"]
    assert rr.NoOpReranker().model_name == "none"


def test_cross_encoder_sorts_by_score_then_truncates(make_chunk):
    # Build without __init__ so no ONNX model is loaded; inject a fake encoder.
    ce = rr.CrossEncoderReranker.__new__(rr.CrossEncoderReranker)
    ce.model_name = "fake"

    class FakeEncoder:
        def rerank(self, query, texts):
            return [0.1, 0.9, 0.5][: len(texts)]

    ce._encoder = FakeEncoder()
    chunks = [make_chunk("a"), make_chunk("b"), make_chunk("c")]

    out = ce.rerank("q", chunks, top_k=2)

    assert [c.chunk_id for c in out] == ["b", "c"]  # 0.9 then 0.5
    assert out[0].score == 0.9  # cross-encoder score replaces the retrieval score


def test_cross_encoder_handles_empty_input():
    ce = rr.CrossEncoderReranker.__new__(rr.CrossEncoderReranker)
    ce._encoder = object()  # never called
    assert ce.rerank("q", [], top_k=3) == []


def test_get_reranker_is_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(rr.settings, "rerank_enabled", False)
    rr.get_reranker.cache_clear()
    try:
        assert isinstance(rr.get_reranker(), rr.NoOpReranker)
    finally:
        rr.get_reranker.cache_clear()


def test_get_reranker_builds_cross_encoder_with_configured_model(monkeypatch):
    built = {}

    class StubCrossEncoder:
        def __init__(self, model_name):
            built["model"] = model_name

    monkeypatch.setattr(rr, "CrossEncoderReranker", StubCrossEncoder)
    monkeypatch.setattr(rr.settings, "rerank_enabled", True)
    monkeypatch.setattr(rr.settings, "reranker_model", "configured/model")
    rr.get_reranker.cache_clear()
    try:
        reranker = rr.get_reranker()
        assert isinstance(reranker, StubCrossEncoder)
        assert built["model"] == "configured/model"  # wired from settings
    finally:
        rr.get_reranker.cache_clear()
