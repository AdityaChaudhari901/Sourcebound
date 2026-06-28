"""Request-scoped middleware: correlation id + access logging, security response
headers, and Redis-backed rate limiting.

Assigns a ``request_id`` to every request (honoring an inbound ``X-Request-ID``
if present), binds it to the structlog context so all logs in the request carry
it, echoes it back on the response, and emits one access log line.
"""

from __future__ import annotations

import hashlib
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("http.access")

REQUEST_ID_HEADER = "X-Request-ID"
# Probes must never be throttled or they cause false "unhealthy" signals.
_RATE_LIMIT_EXEMPT = {"/health", "/ready"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info("request_completed", status_code=response.status_code)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security response headers (defense-in-depth for the browser)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # HSTS only makes sense (and is only honored) over HTTPS.
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if settings.hsts_max_age and (request.url.scheme == "https" or forwarded_proto == "https"):
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.hsts_max_age}; includeSubDomains",
            )
        return response


def _client_identity(request: Request) -> str:
    """Bucket key: per API token/JWT when present, else per client IP.

    Runs before route auth resolves, so we key on the raw credential (hashed, never
    logged) to give each caller its own bucket; anonymous traffic falls back to IP.
    """
    auth = request.headers.get("authorization")
    if auth:
        return "tok:" + hashlib.sha256(auth.encode()).hexdigest()[:32]
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return "ip:" + ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limit (per minute) per caller, backed by Redis.

    Fails **open**: if Redis is unreachable the request is allowed — rate limiting
    must never take the API down. Returns the standard error envelope on 429.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled or request.url.path in _RATE_LIMIT_EXEMPT:
            return await call_next(request)

        identity = _client_identity(request)
        window = int(time.time()) // 60
        key = f"ratelimit:{identity}:{window}"
        try:
            count = await get_redis().incr(key)
            if count == 1:
                await get_redis().expire(key, 60)
        except Exception as exc:  # noqa: BLE001 - never fail a request over rate limiting
            logger.warning("rate_limit_unavailable", error=str(exc))
            return await call_next(request)

        if count > settings.rate_limit_per_minute:
            request_id = getattr(request.state, "request_id", None)
            logger.info("rate_limited", identity=identity, count=count)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Rate limit exceeded. Try again shortly.",
                        "request_id": request_id,
                    }
                },
            )
        return await call_next(request)
