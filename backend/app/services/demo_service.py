"""Guest demo workspace.

A single shared, read-only tenant seeded with sample docs so visitors can try
cited Q&A without signing up. The demo principal is identified by its fixed email
(``DEMO_EMAIL``) and blocked from mutations by ``app.api.deps.forbid_demo``.

Seeding reuses the synchronous ingestion path (parse → chunk → embed → index) and
is idempotent, so it self-heals if the corpus is ever emptied.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.database.models import Document, DocumentStatus, SourceType, Tenant, User
from app.database.session import sync_session
from app.services.ingestion_service import _index_document

DEMO_EMAIL = "demo@sourcebound.local"
DEMO_TENANT_NAME = "Demo workspace"
_FIXTURES = Path(__file__).resolve().parent.parent / "demo_fixtures"


async def ensure_demo_user(db: AsyncSession) -> User:
    """Idempotently provision the demo tenant + user; return the user."""
    user = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None:
        return user
    tenant = Tenant(name=DEMO_TENANT_NAME)
    db.add(tenant)
    await db.flush()
    # Password is random and unused — the demo is entered via POST /auth/demo, not login.
    user = User(
        tenant_id=tenant.id,
        email=DEMO_EMAIL,
        password_hash=hash_password(uuid.uuid4().hex),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def seed_demo_corpus_sync(tenant_id: uuid.UUID) -> None:
    """Ingest the sample docs into the demo tenant (idempotent, synchronous).

    Runs off the event loop (call via ``run_in_threadpool``) since the ingestion
    path embeds and indexes synchronously.
    """
    for path in sorted(_FIXTURES.glob("*.md")):
        with sync_session() as db:
            exists = db.scalar(
                select(Document).where(
                    Document.tenant_id == tenant_id, Document.uri == path.name
                )
            )
            if exists is not None:
                continue
            doc = Document(
                tenant_id=tenant_id,
                source_type=SourceType.MARKDOWN,
                uri=path.name,
                title=path.stem.replace("-", " ").title(),
                status=DocumentStatus.PENDING,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            doc_id = doc.id

        _index_document(
            doc_id,
            tenant_id=tenant_id,
            filename=path.name,
            content=path.read_bytes(),
            content_type="text/markdown",
            source_uri=path.name,
        )
        with sync_session() as db:
            doc = db.get(Document, doc_id)
            doc.status = DocumentStatus.READY
            db.commit()


def issue_demo_token(user: User) -> str:
    return create_access_token(str(user.id))
