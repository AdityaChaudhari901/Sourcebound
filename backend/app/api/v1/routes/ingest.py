"""Ingestion endpoints (asynchronous).

- POST /api/v1/ingest       : create document + job, enqueue the pipeline, return job id (202).
- GET  /api/v1/ingest/{id}  : poll job status.

Thin router: create rows on the async session, hand the file bytes to a Celery
task, and return immediately. The heavy parse/chunk/embed/index work runs in a
worker, off the request path.
"""

from __future__ import annotations

import base64
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status
from sqlalchemy import func, select

from app.core.errors import NotFoundError, UnsupportedMediaTypeError
from app.database.models import Chunk, Document, DocumentStatus, IngestionJob, IngestionState
from app.database.session import DbSession
from app.rag.parsing import UnsupportedFileType, detect_source_type
from app.schemas.ingestion import IngestEnqueuedResponse, IngestJobStatus
from app.workers.tasks import ingest_document as ingest_document_task

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestEnqueuedResponse)
async def ingest(
    db: DbSession,
    file: UploadFile = File(..., description="PDF or Markdown file."),
    source_uri: str | None = Form(None),
    title: str | None = Form(None),
) -> IngestEnqueuedResponse:
    content = await file.read()
    try:
        source_type = detect_source_type(file.filename, file.content_type)
    except UnsupportedFileType as exc:
        raise UnsupportedMediaTypeError(str(exc)) from exc

    source = source_uri or file.filename or "unknown"
    document = Document(
        source_type=source_type, uri=source, title=title, status=DocumentStatus.PENDING
    )
    db.add(document)
    await db.flush()  # assign document.id

    job = IngestionJob(document_id=document.id, state=IngestionState.QUEUED)
    db.add(job)
    await db.flush()
    await db.commit()

    ingest_document_task.delay(
        str(job.id),
        str(document.id),
        file.filename or "upload",
        file.content_type or "",
        base64.b64encode(content).decode("ascii"),
        source,
    )
    return IngestEnqueuedResponse(
        job_id=job.id, document_id=document.id, state=job.state.value
    )


@router.get("/{job_id}", response_model=IngestJobStatus)
async def ingest_status(job_id: UUID, db: DbSession) -> IngestJobStatus:
    job = await db.get(IngestionJob, job_id)
    if job is None:
        raise NotFoundError(f"Ingestion job {job_id} not found")

    chunk_count = await db.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == job.document_id)
    )
    return IngestJobStatus(
        job_id=job.id,
        document_id=job.document_id,
        state=job.state.value,
        error=job.error,
        chunk_count=chunk_count or 0,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
