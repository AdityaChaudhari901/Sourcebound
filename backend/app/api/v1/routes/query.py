"""Query endpoints — naive→corrective RAG, now conversation-aware.

Both endpoints accept an optional conversation_id, carry bounded prior context
into generation, persist the user + assistant turns, and return the
conversation_id plus the assistant message_id (the feedback target).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentPrincipal
from app.database.models import MessageRole
from app.database.session import DbSession
from app.schemas.query import CitationOut, QueryRequest, QueryResponse
from app.services import conversation_service
from app.services.query_service import (
    Citation,
    FinalResult,
    TokenChunk,
    answer_question,
    stream_answer,
)
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/query", tags=["query"])


def _citation_dicts(citations: list[Citation]) -> list[dict]:
    return [
        {"source_uri": c.source_uri, "chunk_id": c.chunk_id, "snippet": c.snippet, "external": c.external}
        for c in citations
    ]


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest, principal: CurrentPrincipal, db: DbSession) -> QueryResponse:
    conversation = await conversation_service.get_or_create_conversation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        conversation_id=request.conversation_id,
    )
    history = await conversation_service.load_recent_history(db, conversation_id=conversation.id)
    await conversation_service.add_message(
        db, conversation_id=conversation.id, role=MessageRole.USER, content=request.question
    )

    started = time.perf_counter()
    result = await run_in_threadpool(
        answer_question,
        request.question,
        tenant_id=str(principal.tenant_id),
        k=request.k,
        history=history,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    citation_dicts = _citation_dicts(result.citations)
    assistant = await conversation_service.add_message(
        db,
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.answer,
        citations=citation_dicts or None,
        latency_ms=latency_ms,
    )
    await db.commit()

    return QueryResponse(
        answer=result.answer,
        citations=[CitationOut(**c) for c in citation_dicts],
        conversation_id=conversation.id,
        message_id=assistant.id,
        grounding=result.grounding,
        self_corrected=result.self_corrected,
        used_web_search=result.used_web_search,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def query_stream(
    request: QueryRequest, principal: CurrentPrincipal, db: DbSession
) -> StreamingResponse:
    conversation = await conversation_service.get_or_create_conversation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        conversation_id=request.conversation_id,
    )
    history = await conversation_service.load_recent_history(db, conversation_id=conversation.id)
    await conversation_service.add_message(
        db, conversation_id=conversation.id, role=MessageRole.USER, content=request.question
    )
    await db.commit()

    conversation_id = conversation.id
    tenant_id = str(principal.tenant_id)

    def event_stream() -> Iterator[str]:
        started = time.perf_counter()
        try:
            for event in stream_answer(
                request.question, tenant_id=tenant_id, k=request.k, history=history
            ):
                if isinstance(event, TokenChunk):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, FinalResult):
                    citation_dicts = _citation_dicts(event.citations)
                    # Persist the assistant turn from the (sync) generator.
                    message_id = conversation_service.add_message_sync(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=event.answer,
                        citations=citation_dicts or None,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                    yield _sse(
                        "citations",
                        {
                            "answer": event.answer,
                            "citations": citation_dicts,
                            "conversation_id": str(conversation_id),
                            "message_id": str(message_id),
                            "grounding": event.grounding,
                            "self_corrected": event.self_corrected,
                            "used_web_search": event.used_web_search,
                        },
                    )
            yield _sse("done", {})
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
