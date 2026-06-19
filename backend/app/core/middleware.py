"""Request-scoped middleware: correlation id + access logging.

Assigns a ``request_id`` to every request (honoring an inbound ``X-Request-ID``
if present), binds it to the structlog context so all logs in the request carry
it, echoes it back on the response, and emits one access log line.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("http.access")

REQUEST_ID_HEADER = "X-Request-ID"


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
