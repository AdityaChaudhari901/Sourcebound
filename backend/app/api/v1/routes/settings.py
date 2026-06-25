"""Read-only settings endpoint for the Settings page (auth-gated, non-secret)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentPrincipal
from app.core.config import settings
from app.schemas.settings import (
    FeaturesInfo,
    ProvidersInfo,
    RetrievalInfo,
    SettingsInfo,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/info", response_model=SettingsInfo)
async def settings_info(principal: CurrentPrincipal) -> SettingsInfo:
    return SettingsInfo(
        environment=settings.environment,
        app_version=settings.app_version,
        qdrant_collection=settings.qdrant_collection,
        providers=ProvidersInfo(
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_temperature=settings.llm_temperature,
            vertex_project=settings.vertex_project,
            vertex_region=settings.vertex_region,
            embedding_provider=settings.embedding_provider,
            embedding_model=settings.embedding_model,
            sparse_embedding_model=settings.sparse_embedding_model,
            reranker_model=settings.reranker_model,
            rerank_enabled=settings.rerank_enabled,
        ),
        retrieval=RetrievalInfo(
            retriever_mode=settings.retriever_mode,
            retrieve_top_n=settings.retrieve_top_n,
            query_top_k=settings.query_top_k,
            max_query_retries=settings.max_query_retries,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        ),
        features=FeaturesInfo(
            web_search_enabled=settings.web_search_enabled,
            web_search_configured=settings.web_search_configured,
            langfuse_enabled=settings.langfuse_enabled,
            langfuse_configured=settings.langfuse_configured,
            langfuse_host=settings.langfuse_host,
        ),
    )
