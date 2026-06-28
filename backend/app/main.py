"""FastAPI application factory for Sourcebound.

Wires the lifespan, CORS, request-context middleware, exception handlers, and
mounts the health endpoint plus the versioned ``/api/v1`` router. No business
logic lives here.
"""

from __future__ import annotations

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "app_startup",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    configure_langfuse()  # init tracing (no-op if unconfigured); verifies connectivity
    # Other resource init (db pool, redis, qdrant) is wired in later slices.
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
