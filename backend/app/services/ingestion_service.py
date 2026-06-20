"""Synchronous document ingestion: parse -> chunk -> embed -> upsert -> persist.

Blocking by design (no asyncio / no Celery yet); the route runs it in a worker
thread. Written so it converts cleanly to a Celery task later: plain inputs, a
sync DB session, and providers behind interfaces.

Write order is chosen for consistency: persist rows (flush, not commit) -> upsert
vectors -> commit. If the upsert fails, the DB transaction rolls back; if the
commit fails after a successful upsert, the just-written vectors are deleted so
Qdrant and Postgres don't drift.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import models

from app.core.config import settings
from app.core.logging import get_logger
from app.database.models import Chunk, Document, DocumentStatus, SourceType
from app.database.session import sync_session
from app.rag.chunking import chunk_blocks
from app.rag.parsing import parse
from app.rag.providers.embeddings import get_embedding_provider
from app.vectorstore.qdrant import (
    delete_points,
    ensure_collection,
    get_qdrant_client,
    upsert_points,
)

logger = get_logger(__name__)


class EmptyDocumentError(Exception):
    """Raised when parsing/chunking yields no usable text."""


@dataclass(frozen=True)
class IngestionResult:
    document_id: uuid.UUID
    chunk_count: int
    source_type: SourceType
    title: str | None


def ingest_document(
    *,
    filename: str | None,
    content: bytes,
    content_type: str | None,
    source_uri: str | None = None,
    title: str | None = None,
) -> IngestionResult:
    source_type, blocks = parse(filename=filename, content=content, content_type=content_type)
    chunks = chunk_blocks(blocks)
    if not chunks:
        raise EmptyDocumentError("No extractable text found in the document.")

    source = source_uri or filename or "unknown"

    embedder = get_embedding_provider()
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])

    qdrant = get_qdrant_client()
    ensure_collection(qdrant, settings.qdrant_collection, embedder.dimension)

    with sync_session() as db:
        document = Document(
            source_type=source_type,
            uri=source,
            title=title,
            status=DocumentStatus.READY,
        )
        db.add(document)
        db.flush()  # assign document.id

        chunk_rows = [
            Chunk(
                document_id=document.id,
                heading_path=chunk.heading_path,
                qdrant_point_id=uuid.uuid4(),
                position=chunk.position,
            )
            for chunk in chunks
        ]
        db.add_all(chunk_rows)
        db.flush()  # assign chunk.id

        points = [
            models.PointStruct(
                id=str(row.qdrant_point_id),
                vector=vector,
                payload={
                    "document_id": str(document.id),
                    "chunk_id": str(row.id),
                    "heading_path": chunk.heading_path,
                    "source_uri": source,
                    "text": chunk.text,  # stored for retrieval context + citation snippets
                },
            )
            for row, chunk, vector in zip(chunk_rows, chunks, vectors, strict=True)
        ]

        upsert_points(qdrant, settings.qdrant_collection, points)
        try:
            db.commit()
        except Exception:
            # Roll back vectors so Qdrant doesn't keep orphans the DB never recorded.
            delete_points(qdrant, settings.qdrant_collection, [p.id for p in points])
            raise

        document_id = document.id

    logger.info(
        "document_ingested",
        document_id=str(document_id),
        source_type=source_type.value,
        chunk_count=len(chunk_rows),
    )
    return IngestionResult(
        document_id=document_id,
        chunk_count=len(chunk_rows),
        source_type=source_type,
        title=title,
    )
