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
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class FeedbackRating(str, enum.Enum):
    UP = "up"
    DOWN = "down"


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


# --- Tenancy + auth models ------------------------------------------------------


class Tenant(Base):
    """A workspace. Every user, document, and vector belongs to exactly one."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)  # argon2; never plaintext
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tenant: Mapped[Tenant] = relationship()
    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("uq_users_email", "email", unique=True),
        Index("ix_users_tenant_id", "tenant_id"),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prefix: Mapped[str] = mapped_column(Text, nullable=False)      # display only (non-secret)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)    # sha256 of the key; never plaintext
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="api_keys")

    __table_args__ = (
        Index("uq_api_keys_key_hash", "key_hash", unique=True),  # lookup by hash on every request
        Index("ix_api_keys_user_id", "user_id"),
    )


# --- Models ---------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
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
        # Tenant-scoped listing/queue (tenant_id leads so every query filters by it).
        Index("ix_documents_tenant_status_created", "tenant_id", "status", "created_at"),
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


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (Index("ix_conversations_tenant_user", "tenant_id", "user_id"),)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(_enum_column(MessageRole, length=16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Assistant messages keep their citations for thread replay (list of dicts).
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # answer wall time
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)


class AnswerFeedback(Base):
    __tablename__ = "answer_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[FeedbackRating] = mapped_column(
        _enum_column(FeedbackRating, length=8), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # One feedback per user per answer (re-submitting updates it).
    __table_args__ = (Index("uq_answer_feedback_message_user", "message_id", "user_id", unique=True),)


class EvalRun(Base):
    """One execution of the eval harness over a golden dataset (aggregate scores)."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dataset: Mapped[str] = mapped_column(Text, nullable=False)
    num_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    faithfulness: Mapped[float] = mapped_column(Float, nullable=False)
    answer_relevancy: Mapped[float] = mapped_column(Float, nullable=False)
    context_precision: Mapped[float] = mapped_column(Float, nullable=False)
    context_recall: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # per-question scores


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
