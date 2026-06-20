"""Asynchronous ingestion pipeline body (runs inside the Celery worker).

The API endpoint creates the Document + IngestionJob and enqueues a task; this
module is what the worker executes: mark the job running, run
parse -> chunk -> embed (dense + sparse) -> upsert to Qdrant -> persist Chunk rows,
then mark the job succeeded (or failed). All synchronous — it runs in a worker
process, off the request path.

Why the worker, not the request: embedding is CPU-bound. Running it inside the
async API would block the event loop (one slow embed stalls every other request),
and a large doc would hold the HTTP connection open for seconds. Pushing it to a
worker keeps the API responsive and lets ingestion scale by adding workers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from qdrant_client import models

from app.core.config import settings
from app.core.logging import get_logger
from app.database.models import (
    Chunk,
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionState,
)
from app.database.session import sync_session
from app.rag.chunking import chunk_blocks
from app.rag.parsing import parse
from app.rag.providers.embeddings import (
    get_embedding_provider,
    get_sparse_embedding_provider,
)
from app.vectorstore.qdrant import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    ensure_collection,
    get_qdrant_client,
    upsert_points,
)

logger = get_logger(__name__)


class EmptyDocumentError(Exception):
    """Raised when parsing/chunking yields no usable text."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _index_document(
    document_id: uuid.UUID,
    *,
    filename: str,
    content: bytes,
    content_type: str,
    source_uri: str,
) -> int:
    """parse -> chunk -> embed -> upsert -> persist chunk rows. Returns chunk count."""
    _source_type, blocks = parse(filename=filename, content=content, content_type=content_type)
    chunks = chunk_blocks(blocks)
    if not chunks:
        raise EmptyDocumentError("No extractable text found in the document.")

    texts = [chunk.text for chunk in chunks]
    embedder = get_embedding_provider()
    sparse_embedder = get_sparse_embedding_provider()
    dense_vectors = embedder.embed_documents(texts)
    sparse_vectors = sparse_embedder.embed_documents(texts)

    qdrant = get_qdrant_client()
    ensure_collection(qdrant, settings.qdrant_collection, embedder.dimension)

    with sync_session() as db:
        chunk_rows = [
            Chunk(
                document_id=document_id,
                heading_path=chunk.heading_path,
                qdrant_point_id=uuid.uuid4(),
                position=chunk.position,
            )
            for chunk in chunks
        ]
        db.add_all(chunk_rows)
        db.flush()

        points = [
            models.PointStruct(
                id=str(row.qdrant_point_id),
                vector={
                    DENSE_VECTOR: dense_vec,
                    SPARSE_VECTOR: models.SparseVector(
                        indices=sparse_vec.indices, values=sparse_vec.values
                    ),
                },
                payload={
                    "document_id": str(document_id),
                    "chunk_id": str(row.id),
                    "heading_path": chunk.heading_path,
                    "source_uri": source_uri,
                    "text": chunk.text,
                },
            )
            for row, chunk, dense_vec, sparse_vec in zip(
                chunk_rows, chunks, dense_vectors, sparse_vectors, strict=True
            )
        ]
        upsert_points(qdrant, settings.qdrant_collection, points)
        db.commit()

    return len(chunk_rows)


def process_ingestion_job(
    *,
    job_id: str,
    document_id: str,
    filename: str,
    content: bytes,
    content_type: str,
    source_uri: str,
) -> None:
    """Worker entrypoint: drive an IngestionJob through running -> succeeded/failed."""
    job_uuid = uuid.UUID(job_id)
    doc_uuid = uuid.UUID(document_id)

    with sync_session() as db:
        job = db.get(IngestionJob, job_uuid)
        document = db.get(Document, doc_uuid)
        if job is None or document is None:
            logger.error("ingest_job_missing", job_id=job_id, document_id=document_id)
            return
        job.state = IngestionState.RUNNING
        job.started_at = _now()
        document.status = DocumentStatus.PROCESSING
        db.commit()

    try:
        chunk_count = _index_document(
            doc_uuid,
            filename=filename,
            content=content,
            content_type=content_type,
            source_uri=source_uri,
        )
    except Exception as exc:  # noqa: BLE001 - record failure on the job, then re-raise
        with sync_session() as db:
            job = db.get(IngestionJob, job_uuid)
            document = db.get(Document, doc_uuid)
            if job is not None:
                job.state = IngestionState.FAILED
                job.error = str(exc)[:1000]
                job.finished_at = _now()
            if document is not None:
                document.status = DocumentStatus.FAILED
            db.commit()
        logger.error("ingest_job_failed", job_id=job_id, error=str(exc))
        raise

    with sync_session() as db:
        job = db.get(IngestionJob, job_uuid)
        document = db.get(Document, doc_uuid)
        if job is not None:
            job.state = IngestionState.SUCCEEDED
            job.finished_at = _now()
        if document is not None:
            document.status = DocumentStatus.READY
        db.commit()
    logger.info("ingest_job_done", job_id=job_id, chunk_count=chunk_count)
