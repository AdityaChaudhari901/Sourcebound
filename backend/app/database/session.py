"""Async database engine, session factory, and the FastAPI session dependency.

One engine (with a connection pool) per process; one short-lived session per
request via ``get_db_session``. Routers/services depend on ``DbSession``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# libpq-style query params that managed Postgres (e.g. Neon) appends to its URL but
# the SQLAlchemy asyncpg/psycopg drivers don't accept as connect kwargs.
_LIBPQ_SSL_PARAMS = {"sslmode", "channel_binding", "sslrootcert", "sslcert", "sslkey"}
_LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1", "postgres"}


def _prepare_url(url: str) -> tuple[str, bool]:
    """Strip libpq SSL params from a Postgres URL and report whether SSL is needed.

    Lets you paste a managed connection string (Neon: ``...?sslmode=require&
    channel_binding=require``) almost verbatim — SSL is then enabled via
    ``connect_args`` per-driver, which both asyncpg and psycopg accept.
    """
    parts = urlsplit(url)
    params = parse_qsl(parts.query)
    require_ssl = parts.hostname not in _LOCAL_HOSTS or any(
        k == "sslmode" and v not in ("disable", "allow") for k, v in params
    )
    kept = [(k, v) for k, v in params if k not in _LIBPQ_SSL_PARAMS]
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))
    return clean, require_ssl


_async_url, _ssl_required = _prepare_url(settings.database_url)

engine = create_async_engine(
    _async_url,
    echo=settings.db_echo,
    pool_pre_ping=True,  # drop dead connections instead of erroring mid-request
    future=True,
    # asyncpg: ssl=True uses a verifying default context (works with Neon's certs).
    # statement_cache_size=0 keeps Neon's PgBouncer pooled endpoint happy.
    connect_args={"ssl": True, "statement_cache_size": 0} if _ssl_required else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # objects stay usable after commit (e.g. in the response)
    autoflush=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session; rolls back and closes on the way out."""
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    """Close the connection pool on application shutdown."""
    await engine.dispose()


# Inject with: `async def handler(db: DbSession): ...`
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# --- Synchronous session (for the blocking ingestion service) -------------------
# Used by code that runs in a worker thread (run_in_threadpool), where an async
# session would have no event loop. Swapped for the async path when ingestion
# moves to Celery later.

_sync_url, _sync_ssl = _prepare_url(settings.sync_database_url)
sync_engine = create_engine(
    _sync_url,
    pool_pre_ping=True,
    future=True,
    # psycopg understands sslmode (not asyncpg's ssl kwarg).
    connect_args={"sslmode": "require"} if _sync_ssl else {},
)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, autoflush=False)


@contextmanager
def sync_session() -> Iterator[Session]:
    """Yield a synchronous session; rolls back on error, always closes."""
    session = SyncSessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
