"""POST /api/v1/ingest — upload a PDF or Markdown file and ingest it.

Thin router: read the upload, run the blocking ingestion service in a worker
thread (so the event loop isn't blocked), and shape the response. Domain errors
are translated to the standard error envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.errors import UnsupportedMediaTypeError, ValidationAppError
from app.rag.parsing import UnsupportedFileType
from app.schemas.ingestion import IngestResponse
from app.services.ingestion_service import EmptyDocumentError, ingest_document

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(..., description="PDF or Markdown file."),
    source_uri: str | None = Form(None, description="Canonical source URI (defaults to filename)."),
    title: str | None = Form(None, description="Optional document title."),
) -> IngestResponse:
    content = await file.read()

    try:
        result = await run_in_threadpool(
            ingest_document,
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            source_uri=source_uri,
            title=title,
        )
    except UnsupportedFileType as exc:
        raise UnsupportedMediaTypeError(str(exc)) from exc
    except EmptyDocumentError as exc:
        raise ValidationAppError(str(exc)) from exc

    return IngestResponse(
        document_id=result.document_id,
        chunk_count=result.chunk_count,
        source_type=result.source_type.value,
        title=result.title,
        status="ready",
    )
