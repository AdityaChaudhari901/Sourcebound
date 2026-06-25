"""Integration fixtures: real Postgres + Qdrant in throwaway containers.

Requires a running Docker daemon. The whole tier is marked `integration` (see the
test module) so it can be deselected with `-m "not integration"`.

Wiring: point the app's Qdrant client + synchronous DB engine at the containers,
create the schema, and use a NoOp reranker + zero rewrite retries so retrieval
behaviour is deterministic and no heavy cross-encoder is downloaded. The real BGE
embeddings ARE used — that's the point of the integration test.
"""

from __future__ import annotations

import time
import urllib.request
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def _postgres():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg


@pytest.fixture(scope="session")
def _qdrant():
    container = DockerContainer("qdrant/qdrant:v1.12.4").with_exposed_ports(6333)
    container.start()
    url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(6333)}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{url}/readyz", timeout=1)
            break
        except Exception:  # noqa: BLE001 - container still starting
            time.sleep(1)
    else:
        container.stop()
        raise RuntimeError("Qdrant did not become ready in time")
    container.sb_url = url
    yield container
    container.stop()


@pytest.fixture(scope="session", autouse=True)
def _wire_infra(_postgres, _qdrant):
    import app.database.models  # noqa: F401 - registers tables on Base.metadata
    from app.core.config import settings
    from app.database import session as db_session
    from app.database.base import Base
    from app.rag.reranking import get_reranker
    from app.vectorstore.qdrant import get_qdrant_client

    overrides = {
        "qdrant_url": _qdrant.sb_url,
        "qdrant_collection": "test_chunks",
        "retriever_mode": "hybrid",
        "rerank_enabled": False,
        "web_search_enabled": False,
        "max_query_retries": 0,
    }
    saved = {k: getattr(settings, k) for k in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)
    get_qdrant_client.cache_clear()
    get_reranker.cache_clear()

    saved_engine = db_session.sync_engine
    saved_factory = db_session.SyncSessionLocal
    engine = create_engine(_postgres.get_connection_url(), future=True)
    Base.metadata.create_all(engine)
    db_session.sync_engine = engine
    db_session.SyncSessionLocal = sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )

    yield

    # Restore process-global state so a later (unit) test in the same run is clean.
    for key, value in saved.items():
        setattr(settings, key, value)
    db_session.sync_engine = saved_engine
    db_session.SyncSessionLocal = saved_factory
    get_qdrant_client.cache_clear()
    get_reranker.cache_clear()
    engine.dispose()


@pytest.fixture(scope="session")
def seeded(_wire_infra):
    """Two tenants; one document ingested (real embeddings + real Qdrant) for tenant A."""
    from app.database.models import Document, DocumentStatus, SourceType, Tenant
    from app.database.session import sync_session
    from app.services.ingestion_service import _index_document

    content = (
        b"# Payments runbook\n\n"
        b"Rotate the payments service secret every 90 days using "
        b"`vault rotate payments`. Store secrets only in the secret manager.\n"
    )
    with sync_session() as db:
        a, b = Tenant(name="tenant-a"), Tenant(name="tenant-b")
        db.add_all([a, b])
        db.commit()
        a_id, b_id = a.id, b.id
        doc = Document(
            tenant_id=a_id,
            source_type=SourceType.MARKDOWN,
            uri="runbook.md",
            title="Payments runbook",
            status=DocumentStatus.PENDING,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    chunk_count = _index_document(
        doc_id,
        tenant_id=a_id,
        filename="runbook.md",
        content=content,
        content_type="text/markdown",
        source_uri="runbook.md",
    )
    return SimpleNamespace(a=a_id, b=b_id, doc_id=doc_id, chunk_count=chunk_count)
