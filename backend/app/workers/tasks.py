"""Celery tasks. The file bytes ride in the message (base64) so the worker needs
no shared filesystem with the API — only the same Redis broker.

(For large corpora you'd hand off via object storage / a shared volume instead of
the broker; bytes-in-message is fine for the document sizes here.)
"""

from __future__ import annotations

import base64

from app.workers.celery_app import celery_app
from app.services.ingestion_service import process_ingestion_job, reindex_document


@celery_app.task(name="app.workers.tasks.ingest_document")
def ingest_document(
    job_id: str,
    document_id: str,
    filename: str,
    content_type: str,
    content_b64: str,
    source_uri: str,
) -> None:
    process_ingestion_job(
        job_id=job_id,
        document_id=document_id,
        filename=filename,
        content=base64.b64decode(content_b64),
        content_type=content_type,
        source_uri=source_uri,
    )


@celery_app.task(name="app.workers.tasks.reindex_document")
def reindex_document_task(job_id: str, document_id: str) -> None:
    reindex_document(job_id=job_id, document_id=document_id)
