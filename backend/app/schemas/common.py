"""Shared schemas — the canonical error envelope (also documents the shape in OpenAPI)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable, machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    request_id: str | None = Field(None, description="Correlation id for this request.")
    details: dict[str, Any] | None = Field(None, description="Optional structured context.")


class ErrorResponse(BaseModel):
    error: ErrorDetail
