"""Feedback endpoint — 👍/👎 (+ optional comment) per assistant answer, stored as
eval data. Tenant-scoped and idempotent (re-submitting updates the rating)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentPrincipal
from app.database.models import FeedbackRating
from app.database.session import DbSession
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services import conversation_service

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest, principal: CurrentPrincipal, db: DbSession
) -> FeedbackResponse:
    feedback = await conversation_service.record_feedback(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        message_id=payload.message_id,
        rating=FeedbackRating(payload.rating),
        comment=payload.comment,
    )
    return FeedbackResponse(
        id=feedback.id, message_id=feedback.message_id, rating=feedback.rating.value
    )
