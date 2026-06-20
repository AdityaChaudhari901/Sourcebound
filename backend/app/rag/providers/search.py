"""Web search provider interface and the default (Tavily) implementation.

The corrective graph uses this only as a last-resort fallback when internal
retrieval can't ground the answer. Behind an interface so the provider is
swappable, and gated by config so the graph never reaches for the network unless
web search is explicitly enabled with a key.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import settings
from app.core.errors import AppError


class WebSearchError(AppError):
    code, status_code = "web_search_failed", 502


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    content: str


@runtime_checkable
class SearchProvider(Protocol):
    def search(self, query: str, *, max_results: int) -> list[WebResult]: ...


class TavilySearchProvider:
    def __init__(self, api_key: str) -> None:
        from tavily import TavilyClient

        self._client = TavilyClient(api_key=api_key)

    def search(self, query: str, *, max_results: int) -> list[WebResult]:
        try:
            response = self._client.search(
                query=query, max_results=max_results, search_depth="basic"
            )
        except Exception as exc:  # noqa: BLE001
            raise WebSearchError(f"Web search failed: {exc}") from exc
        return [
            WebResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
            )
            for r in response.get("results", [])
        ]


@lru_cache(maxsize=1)
def get_search_provider() -> SearchProvider:
    if not settings.web_search_configured:
        raise WebSearchError("Web search is not configured (set WEB_SEARCH_ENABLED + TAVILY_API_KEY).")
    if settings.web_search_provider == "tavily":
        return TavilySearchProvider(settings.tavily_api_key.get_secret_value())  # type: ignore[union-attr]
    raise WebSearchError(f"Unknown web search provider: {settings.web_search_provider!r}")
