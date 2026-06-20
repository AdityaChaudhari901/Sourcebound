"""SQLAlchemy ORM models for the metadata store (single-tenant for now).

Vectors live in Qdrant; *facts and relationships* live here. Design choices:
- UUID primary keys (DB-generated via ``gen_random_uuid()``) — safe to expose,
  no enumeration, and ready for distributed/multi-tenant work later.
- ``timestamptz`` everywhere (UTC), never naive timestamps.
- States stored as text + CHECK (``native_enum=False``) rather than native PG
  enums — adding a new state is a CHECK change, not a fragile ALTER TYPE.
- Foreign keys are explicitly indexed and given ON DELETE behavior.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# --- Enumerations (rendered as VARCHAR + CHECK) ---------------------------------


class SourceType(str, enum.Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    CODE = "code"
    NOTION = "notion"
    URL = "url"
    TEXT = "text"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"      # registered, not yet ingested
    PROCESSING = "processing"
    READY = "ready"          # chunked + indexed, queryable
    FAILED = "failed"


class IngestionState(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _enum_column(py_enum: type[enum.Enum], *, length: int) -> SAEnum:
    """A text-backed enum with a DB CHECK constraint (no native PG enum type)."""
    return SAEnum(
        py_enum,
        native_enum=False,
        create_constraint=True,  # emit `CHECK (col IN (...))` — DB enforces valid states
        length=length,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
    )


# --- Models ---------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_type: Mapped[SourceType] = mapped_column(
        _enum_column(SourceType, length=16), nullable=False
    )
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        _enum_column(DocumentStatus, length=16),
        nullable=False,
        server_default=DocumentStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # The *source's* last-modified time (for staleness detection), not a row audit.
    last_modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_documents_uri", "uri"),                         # dedupe / staleness lookup
        Index("ix_documents_status_created", "status", "created_at"),  # status queue + sort
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[IngestionState] = mapped_column(
        _enum_column(IngestionState, length=16),
        nullable=False,
        server_default=IngestionState.QUEUED.value,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship(back_populates="jobs")

    __table_args__ = (
        # Latest-job-per-document and the state queue.
        Index("ix_ingestion_jobs_document_created", "document_id", "created_at"),
        Index("ix_ingestion_jobs_state_created", "state", "created_at"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # Heading hierarchy as a delimited path (e.g. "Setup / Local / Payments").
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The Qdrant point this chunk was indexed as; NULL until embedding/indexing runs.
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        # Ordering within a doc is unique; this also serves as the document_id FK index.
        Index("uq_chunks_document_position", "document_id", "position", unique=True),
        # Reverse map from a vector hit to its chunk (citations). Unique when present.
        Index("uq_chunks_qdrant_point_id", "qdrant_point_id", unique=True),
    )
