"""FastAPI application factory for Sourcebound.

Wires the lifespan, CORS, request-context middleware, exception handlers, and
mounts the health endpoint plus the versioned ``/api/v1`` router. No business
logic lives here.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router as api_v1_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.observability import configure_langfuse, shutdown_langfuse
from app.core.redis import close_redis
from app.database.session import dispose_engine

logger = get_logger(__name__)


def _warmup() -> None:
    """Pre-load embedding/rerank models and warm the LLM/embedding clients so the
    first real query isn't a cold start (model downloads + first Vertex auth ~12s).
    Best-effort: never blocks or fails startup.
    """
    try:
        from app.rag.providers.embeddings import (
            get_embedding_provider,
            get_sparse_embedding_provider,
        )
        from app.rag.reranking import get_reranker

        get_embedding_provider().embed_query("warmup")  # Vertex client + auth
        get_sparse_embedding_provider().embed_query("warmup")  # BM25 model
        get_reranker()  # cross-encoder model (no-op if rerank disabled)
        logger.info("warmup_complete")
    except Exception as exc:  # noqa: BLE001  (warmup must never crash the app)
        logger.warning("warmup_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "app_startup",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    configure_langfuse()  # init tracing (no-op if unconfigured); verifies connectivity
    # Warm models/clients off the event loop so startup (and /health) isn't blocked.
    app.state.warmup_task = asyncio.create_task(asyncio.to_thread(_warmup))
    yield
    shutdown_langfuse()  # flush buffered traces before exit
    await close_redis()  # close the app-side Redis client
    await dispose_engine()  # close the DB connection pool
    logger.info("app_shutdown", service=settings.app_name)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Citation-grounded KnowledgeOps RAG platform.",
        lifespan=lifespan,
    )

    # Middleware order matters. Starlette runs the LAST-added middleware OUTERMOST,
    # so we add inner->outer. Effective request order:
    #   TrustedHost -> [HTTPSRedirect] -> [SecurityHeaders] -> RequestContext
    #     -> CORS -> RateLimit -> app
    # RateLimit is inside RequestContext (so its 429 carries the request_id) and
    # inside CORS (so the 429 gets CORS headers for the browser).
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    if settings.security_headers_enabled:
        app.add_middleware(SecurityHeadersMiddleware)
    if settings.force_https:
        app.add_middleware(HTTPSRedirectMiddleware)
    if settings.trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
