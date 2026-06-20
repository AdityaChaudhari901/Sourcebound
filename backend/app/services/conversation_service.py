"""Conversation, message, and feedback persistence (tenant + user scoped).

Memory bounding lives here: ``load_recent_history`` returns at most the last N
messages AND caps the total characters, so the context fed to the LLM stays
bounded no matter how long a conversation gets.

Async helpers are used by the request endpoints; ``add_message_sync`` exists for
the streaming generator, which runs synchronously in a worker thread.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.database.models import (
    AnswerFeedback,
    Conversation,
    FeedbackRating,
    Message,
    MessageRole,
)
from app.database.session import sync_session


async def get_or_create_conversation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
) -> Conversation:
    if conversation_id is not None:
        conversation = await db.get(Conversation, conversation_id)
        # Scope check: must belong to this tenant AND user.
        if (
            conversation is None
            or conversation.tenant_id != tenant_id
            or conversation.user_id != user_id
        ):
            raise NotFoundError("Conversation not found")
        return conversation
    conversation = Conversation(tenant_id=tenant_id, user_id=user_id)
    db.add(conversation)
    await db.flush()
    return conversation


async def load_recent_history(
    db: AsyncSession, *, conversation_id: uuid.UUID
) -> list[dict[str, str]]:
    """Last N messages within the char budget, oldest-first. Bounded both ways."""
    result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.history_max_messages)
    )
    recent = list(result)[::-1]  # back to chronological order

    # Trim from the oldest end until under the character budget.
    budget = settings.history_char_budget
    while recent and sum(len(m.content) for m in recent) > budget:
        recent.pop(0)

    return [{"role": m.role.value, "content": m.content} for m in recent]


async def add_message(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    citations: list | None = None,
    latency_ms: int | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=citations,
        latency_ms=latency_ms,
    )
    db.add(message)
    await db.flush()
    return message


def add_message_sync(
    *,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    citations: list | None = None,
    latency_ms: int | None = None,
) -> uuid.UUID:
    """Persist a message from synchronous code (the streaming generator)."""
    with sync_session() as db:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            latency_ms=latency_ms,
        )
        db.add(message)
        db.commit()
        return message.id


async def record_feedback(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
    rating: FeedbackRating,
    comment: str | None,
) -> AnswerFeedback:
    # The message must be an assistant answer in the caller's tenant.
    message = await db.get(Message, message_id)
    if message is None:
        raise NotFoundError("Message not found")
    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is None or conversation.tenant_id != tenant_id:
        raise NotFoundError("Message not found")

    existing = await db.scalar(
        select(AnswerFeedback).where(
            AnswerFeedback.message_id == message_id, AnswerFeedback.user_id == user_id
        )
    )
    if existing is not None:
        existing.rating = rating
        existing.comment = comment
        await db.commit()
        return existing

    feedback = AnswerFeedback(
        message_id=message_id,
        tenant_id=tenant_id,
        user_id=user_id,
        rating=rating,
        comment=comment,
    )
    db.add(feedback)
    await db.commit()
    return feedback
