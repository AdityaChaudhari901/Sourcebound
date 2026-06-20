"""Async database engine, session factory, and the FastAPI session dependency.

One engine (with a connection pool) per process; one short-lived session per
request via ``get_db_session``. Routers/services depend on ``DbSession``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,  # drop dead connections instead of erroring mid-request
    future=True,
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
