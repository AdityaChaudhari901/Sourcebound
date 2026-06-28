"""App-side async Redis client (rate limiting, readiness checks, caching).

Separate from Celery's broker connection — this is the request-path client. One
client per process; closed on app shutdown.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Return the process-wide async Redis client (created on first use)."""
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    """Close the client on application shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
