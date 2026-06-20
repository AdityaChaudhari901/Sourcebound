"""Schemas for the query endpoint."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question.")
    k: int | None = Field(
        None, ge=1, le=20, description="Top-k chunks to retrieve (defaults to server setting)."
    )
    conversation_id: uuid.UUID | None = Field(
        None, description="Continue an existing conversation; omit to start a new one."
    )


class CitationOut(BaseModel):
    source_uri: str
    chunk_id: str
    snippet: str
    external: bool = False  # True = external web source (source_uri is a URL)


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    conversation_id: uuid.UUID
    message_id: uuid.UUID  # the assistant message — target for feedback
