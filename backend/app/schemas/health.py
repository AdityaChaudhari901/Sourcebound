"""Schemas for the health endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Overall service status.")
    service: str = Field(..., description="Service name.")
    version: str = Field(..., description="Running application version.")
    environment: str = Field(..., description="Deployment environment.")
