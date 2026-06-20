"""Schemas for the query endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question.")
    k: int | None = Field(
        None, ge=1, le=20, description="Top-k chunks to retrieve (defaults to server setting)."
    )


class CitationOut(BaseModel):
    source_uri: str
    chunk_id: str
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
