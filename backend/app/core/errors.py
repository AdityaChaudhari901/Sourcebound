"""Domain error types and the single error->HTTP mapping point.

All errors are rendered through one JSON envelope so clients parse one shape
everywhere:

    {"error": {"code": "...", "message": "...", "request_id": "...", "details": {...}}}

Services raise typed ``AppError`` subclasses; the transport layer maps them to
status codes here and nowhere else.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, domain-level errors with a stable code and status."""

    code: str = "internal_error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    code, status_code = "not_found", status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    code, status_code = "conflict", status.HTTP_409_CONFLICT


class ForbiddenError(AppError):
    code, status_code = "forbidden", status.HTTP_403_FORBIDDEN


class UnauthorizedError(AppError):
    code, status_code = "unauthorized", status.HTTP_401_UNAUTHORIZED


class ValidationAppError(AppError):
    code, status_code = "validation_error", status.HTTP_422_UNPROCESSABLE_ENTITY


# Map common raw HTTP status codes to stable envelope codes.
_HTTP_CODE_MAP: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(
    code: str,
    message: str,
    request_id: str | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    """Register every exception->envelope mapping in one place."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, _request_id(request), exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error",
                "Request validation failed",
                _request_id(request),
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Unexpected failure: log with full context, never leak internals to the client.
        logger.error("unhandled_exception", request_id=_request_id(request), exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "internal_error", "An unexpected error occurred", _request_id(request)
            ),
        )
