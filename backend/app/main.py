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

from app.api.health import router as health_router
from app.api.v1.router import api_router as api_v1_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "app_startup",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    # Resource init (db pool, redis, qdrant, langfuse) is wired in later slices.
    yield
    logger.info("app_shutdown", service=settings.app_name)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Citation-grounded KnowledgeOps RAG platform.",
        lifespan=lifespan,
    )

    # CORS is added first so it stays inside the request-context middleware and
    # still decorates error responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
