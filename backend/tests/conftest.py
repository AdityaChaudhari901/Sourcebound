"""Shared test fakes + factories.

Unit tests mock the LLM, embeddings, retriever, reranker, and web-search providers
so they run fast and deterministically, with no network, no model downloads, and no
containers. The fakes mirror the provider protocols exactly (keyword-only args) so a
drift in a real signature breaks the tests.
"""

from __future__ import annotations

import pytest

from app.rag.retrievers import RetrievedChunk


class FakeLLM:
    """Stand-in for an LLMProvider. `complete` returns a fixed string; `stream`
    yields fixed tokens. Records calls so tests can assert prompt routing."""

    model_name = "fake-llm"

    def __init__(self, *, complete: str = "", tokens: list[str] | None = None) -> None:
        self._complete = complete
        self._tokens = list(tokens or [])
        self.calls: list[tuple[str, str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append(("complete", system, user))
        return self._complete

    def stream(self, *, system: str, user: str):
        self.calls.append(("stream", system, user))
        yield from self._tokens


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.calls: list[tuple[str, int, str]] = []

    def retrieve(self, query: str, *, k: int, tenant_id: str) -> list[RetrievedChunk]:
        self.calls.append((query, k, tenant_id))
        return list(self._chunks)[:k]


class FakeReranker:
    """Returns `ordered` if given (to simulate reordering), else passthrough; both
    truncated to top_k."""

    def __init__(self, ordered: list[RetrievedChunk] | None = None) -> None:
        self._ordered = ordered
        self.calls: list[tuple[str, list[RetrievedChunk], int]] = []

    def rerank(self, query: str, chunks: list[RetrievedChunk], *, top_k: int):
        self.calls.append((query, list(chunks), top_k))
        out = self._ordered if self._ordered is not None else list(chunks)
        return out[:top_k]


class FakeSearchResult:
    def __init__(self, url: str, title: str | None, content: str) -> None:
        self.url = url
        self.title = title
        self.content = content


class FakeSearchProvider:
    def __init__(self, results: list[FakeSearchResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, max_results: int) -> list[FakeSearchResult]:
        self.calls.append((query, max_results))
        return self._results


@pytest.fixture
def make_chunk():
    """Factory for RetrievedChunk with sensible defaults."""

    def _make(
        chunk_id: str,
        *,
        text: str = "some text",
        score: float = 1.0,
        source_uri: str = "doc.md",
        document_id: str = "d1",
        heading_path: str | None = None,
        external: bool = False,
    ) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_uri=source_uri,
            heading_path=heading_path,
            text=text,
            score=score,
            external=external,
        )

    return _make
