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
from sqlalchemy import select

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
    tenant_id: uuid.UUID,
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
                    "tenant_id": str(tenant_id),  # the isolation key; filtered at query time
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
        tenant_id = document.tenant_id  # stamped into every vector payload
        job.state = IngestionState.RUNNING
        job.started_at = _now()
        document.status = DocumentStatus.PROCESSING
        db.commit()

    try:
        chunk_count = _index_document(
            doc_uuid,
            tenant_id=tenant_id,
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


def reindex_document(*, job_id: str, document_id: str) -> None:
    """Re-embed a document's existing chunks and re-upsert them (same point ids).

    We don't store source files, so 're-ingest' means re-index: pull each chunk's
    text from Qdrant, re-embed (dense + sparse), and overwrite the vectors. Useful
    after an embedding-model or chunking change.
    """
    job_uuid = uuid.UUID(job_id)
    doc_uuid = uuid.UUID(document_id)

    with sync_session() as db:
        job = db.get(IngestionJob, job_uuid)
        document = db.get(Document, doc_uuid)
        if job is None or document is None:
            logger.error("reindex_job_missing", job_id=job_id)
            return
        point_ids = [
            str(c.qdrant_point_id)
            for c in db.scalars(
                select(Chunk).where(Chunk.document_id == doc_uuid)
            ).all()
            if c.qdrant_point_id is not None
        ]
        job.state = IngestionState.RUNNING
        job.started_at = _now()
        document.status = DocumentStatus.PROCESSING
        db.commit()

    try:
        qdrant = get_qdrant_client()
        existing = qdrant.retrieve(settings.qdrant_collection, ids=point_ids, with_payload=True)
        texts = [p.payload.get("text", "") for p in existing]
        embedder = get_embedding_provider()
        sparse_embedder = get_sparse_embedding_provider()
        dense_vectors = embedder.embed_documents(texts)
        sparse_vectors = sparse_embedder.embed_documents(texts)
        ensure_collection(qdrant, settings.qdrant_collection, embedder.dimension)
        points = [
            models.PointStruct(
                id=p.id,
                vector={
                    DENSE_VECTOR: dense_vec,
                    SPARSE_VECTOR: models.SparseVector(
                        indices=sparse_vec.indices, values=sparse_vec.values
                    ),
                },
                payload=p.payload,  # unchanged metadata; only the vectors refresh
            )
            for p, dense_vec, sparse_vec in zip(existing, dense_vectors, sparse_vectors, strict=True)
        ]
        if points:
            upsert_points(qdrant, settings.qdrant_collection, points)
    except Exception as exc:  # noqa: BLE001
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
        logger.error("reindex_job_failed", job_id=job_id, error=str(exc))
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
    logger.info("reindex_job_done", job_id=job_id, points=len(point_ids))
