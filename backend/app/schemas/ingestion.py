"""Schemas for the ingestion endpoint."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    document_id: uuid.UUID = Field(..., description="ID of the persisted document.")
    chunk_count: int = Field(..., description="Number of chunks embedded and indexed.")
    source_type: str = Field(..., description="Detected source type (pdf | markdown).")
    title: str | None = Field(None, description="Title, if provided.")
    status: str = Field(..., description="Document status after ingestion.")
