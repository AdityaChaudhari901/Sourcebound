"""Pre-seed the guest demo corpus into the configured datastores.

Run this ONCE against the deployed Postgres + Qdrant (with the embedding/Vertex
env set), because seeding inside the ``POST /auth/demo`` request embeds every
chunk via a slow hosted call (~one request per chunk) and exceeds the request
lifetime on a PaaS. Doing it out-of-band keeps the endpoint instant.

Idempotent: removes any half-indexed (non-``READY``) demo documents, then
(re)seeds every fixture (``seed_demo_corpus_sync`` skips docs already ``READY``).

Usage (env points at the deployed services):
    DATABASE_URL=postgresql+asyncpg://...neon... \\
    QDRANT_URL=https://...:6333 SOURCEBOUND_QDRANT_API_KEY=... \\
    SOURCEBOUND_EMBEDDING_PROVIDER=vertex VERTEX_PROJECT_ID=... VERTEX_REGION=global \\
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-sa.json \\
    python scripts/seed_demo.py
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select

from app.core.security import hash_password
from app.database.models import Chunk, Document, DocumentStatus, Tenant, User
from app.database.session import sync_session
from app.services import demo_service


def main() -> None:
    with sync_session() as db:
        user = db.scalar(select(User).where(User.email == demo_service.DEMO_EMAIL))
        if user is None:
            tenant = Tenant(name=demo_service.DEMO_TENANT_NAME)
            db.add(tenant)
            db.flush()
            user = User(
                tenant_id=tenant.id,
                email=demo_service.DEMO_EMAIL,
                password_hash=hash_password(uuid.uuid4().hex),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        tenant_id = user.tenant_id

        # Drop half-indexed docs so they are re-created and indexed cleanly.
        incomplete = db.scalars(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.status != DocumentStatus.READY,
            )
        ).all()
        for doc in incomplete:
            db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            db.delete(doc)
        db.commit()
        print(f"demo tenant {tenant_id}: removed {len(incomplete)} incomplete document(s)")

    demo_service.seed_demo_corpus_sync(tenant_id)

    with sync_session() as db:
        ready = db.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == tenant_id,
                Document.status == DocumentStatus.READY,
            )
        )
        print(f"READY documents in demo tenant: {ready}")


if __name__ == "__main__":
    main()
