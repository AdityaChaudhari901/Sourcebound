"""Unit tests for weighted Reciprocal Rank Fusion + HybridRetriever wiring."""

from __future__ import annotations

from app.rag.retrievers import HybridRetriever, reciprocal_rank_fusion

from tests.conftest import FakeRetriever


def _ids(chunks):
    return [c.chunk_id for c in chunks]


def test_doc_ranked_high_in_both_lists_wins(make_chunk):
    a, b, c = make_chunk("a"), make_chunk("b"), make_chunk("c")
    dense = [a, b, c]   # a is rank 0
    sparse = [a, c, b]  # a is rank 0 in both
    fused = reciprocal_rank_fusion([(dense, 1.0), (sparse, 1.0)], rrf_k=60, k=3)
    assert fused[0].chunk_id == "a"  # appears top in both -> highest fused score


def test_duplicate_chunk_is_deduplicated_and_scores_sum(make_chunk):
    a = make_chunk("a")
    fused = reciprocal_rank_fusion([([a], 1.0), ([a], 1.0)], rrf_k=60, k=5)
    assert _ids(fused) == ["a"]  # one entry, not two
    # score = weight/(k+1) summed across both lists = 2 * 1/61
    assert fused[0].score == 2 * (1.0 / 61)


def test_weighting_favours_the_heavier_list(make_chunk):
    only_dense = make_chunk("d")
    only_sparse = make_chunk("s")
    # d is rank 0 in dense only; s is rank 0 in sparse only. Heavier dense weight wins.
    fused = reciprocal_rank_fusion(
        [([only_dense], 5.0), ([only_sparse], 1.0)], rrf_k=60, k=2
    )
    assert fused[0].chunk_id == "d"


def test_results_truncated_to_k_and_sorted_descending(make_chunk):
    chunks = [make_chunk(c) for c in "abcde"]
    fused = reciprocal_rank_fusion([(chunks, 1.0)], rrf_k=60, k=3)
    assert len(fused) == 3
    scores = [c.score for c in fused]
    assert scores == sorted(scores, reverse=True)
    # rank 0 ("a") keeps the top fused score
    assert fused[0].chunk_id == "a"


def test_fused_score_replaces_original_score(make_chunk):
    a = make_chunk("a", score=999.0)
    fused = reciprocal_rank_fusion([([a], 1.0)], rrf_k=60, k=1)
    assert fused[0].score != 999.0
    assert fused[0].score == 1.0 / 61


def test_hybrid_retriever_queries_both_at_prefetch_depth_then_fuses(make_chunk):
    shared = make_chunk("shared")
    dense = FakeRetriever([shared, make_chunk("d_only")])
    sparse = FakeRetriever([shared, make_chunk("s_only")])
    hybrid = HybridRetriever(
        dense, sparse, dense_weight=1.0, sparse_weight=1.0, rrf_k=60, prefetch=20
    )

    out = hybrid.retrieve("q", k=2, tenant_id="t1")

    # both sub-retrievers were queried at depth = max(k, prefetch) = 20, same tenant
    assert dense.calls[0] == ("q", 20, "t1")
    assert sparse.calls[0] == ("q", 20, "t1")
    assert len(out) == 2
    # the chunk found by BOTH retrievers should rank first
    assert out[0].chunk_id == "shared"
