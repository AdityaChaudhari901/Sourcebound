"""Schemas for the (async) ingestion endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IngestEnqueuedResponse(BaseModel):
    """Returned immediately from POST /ingest once the job is queued."""

    job_id: uuid.UUID = Field(..., description="Poll GET /ingest/{job_id} for progress.")
    document_id: uuid.UUID
    state: str = Field(..., description="Job state (starts at 'queued').")


class IngestJobStatus(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID
    state: str = Field(..., description="queued | running | succeeded | failed")
    error: str | None = None
    chunk_count: int = Field(0, description="Chunks indexed so far / at completion.")
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
