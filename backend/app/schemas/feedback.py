"""Feedback schema — thumbs up/down + optional comment, per assistant answer."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    message_id: uuid.UUID = Field(..., description="The assistant message being rated.")
    rating: Literal["up", "down"]
    comment: str | None = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    rating: str
