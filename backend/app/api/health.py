"""Health endpoints, mounted at the application root.

- ``/health``  — *liveness*: is the process up? Static, no dependency checks, so a
  transient DB blip never triggers a restart loop. The orchestrator restarts the
  container if this stops responding.
- ``/ready``   — *readiness*: can it serve traffic right now? Checks Postgres,
  Qdrant, and Redis; returns 503 if any dependency is down so the load balancer
  stops routing here without killing the process.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.database.session import AsyncSessionLocal
from app.schemas.health import HealthResponse
from app.vectorstore.qdrant import get_qdrant_client

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


async def _check_database() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))


async def _check_qdrant() -> None:
    # qdrant-client is synchronous; run it off the event loop.
    await run_in_threadpool(get_qdrant_client().get_collections)


async def _check_redis() -> None:
    await get_redis().ping()


@router.get("/ready", summary="Readiness probe (checks dependencies)")
async def ready() -> JSONResponse:
    checks = {"database": _check_database, "qdrant": _check_qdrant, "redis": _check_redis}
    results: dict[str, str] = {}
    healthy = True
    for name, check in checks.items():
        try:
            await check()
            results[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - report which dependency is down
            results[name] = "error"
            healthy = False
            logger.warning("readiness_check_failed", dependency=name, error=str(exc))
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "not_ready", "checks": results},
    )
