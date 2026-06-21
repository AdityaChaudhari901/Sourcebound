"""Schemas for the management pages (Sources, Evaluations, Traces)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    source_type: str
    uri: str
    title: str | None = None
    status: str
    chunk_count: int
    created_at: datetime
    last_modified: datetime | None = None


class ReingestResponse(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID
    state: str


class EvalRunOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    dataset: str
    num_questions: int
    llm_model: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


class TraceOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    snippet: str
    answer: str
    latency_ms: int | None = None
    grounding: float | None = None
    self_corrected: bool = False
    used_web_search: bool = False
    citation_count: int = 0
    est_tokens: int = 0
    est_cost_usd: float = 0.0
