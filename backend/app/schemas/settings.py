"""Read-only settings exposed to the UI.

Security: this surface carries ONLY non-secret configuration. Credentials (API
keys, JWT secret, DB/Redis URLs) are never included — provider readiness is
reported as booleans (`*_configured`) so the UI can show what's wired without
ever transmitting a secret.
"""

from __future__ import annotations

from pydantic import BaseModel


class ProvidersInfo(BaseModel):
    llm_provider: str
    llm_model: str | None
    llm_temperature: float
    vertex_project: str | None
    vertex_region: str
    embedding_provider: str
    embedding_model: str
    sparse_embedding_model: str
    reranker_model: str
    rerank_enabled: bool


class RetrievalInfo(BaseModel):
    retriever_mode: str
    retrieve_top_n: int
    query_top_k: int
    max_query_retries: int
    chunk_size: int
    chunk_overlap: int


class FeaturesInfo(BaseModel):
    web_search_enabled: bool
    web_search_configured: bool
    langfuse_enabled: bool
    langfuse_configured: bool
    langfuse_host: str


class SettingsInfo(BaseModel):
    environment: str
    app_version: str
    qdrant_collection: str
    providers: ProvidersInfo
    retrieval: RetrievalInfo
    features: FeaturesInfo
