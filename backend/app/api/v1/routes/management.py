"""Management endpoints for the Sources, Evaluations, and Traces pages.

All document/trace reads are tenant-scoped; eval runs are pipeline-level (global).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.deps import CurrentPrincipal, NotDemoPrincipal
from app.core.errors import NotFoundError
from app.database.models import (
    Chunk,
    Conversation,
    Document,
    DocumentStatus,
    EvalRun,
    IngestionJob,
    IngestionState,
    Message,
    MessageRole,
)
from app.database.session import DbSession
from app.schemas.management import DocumentOut, EvalRunOut, ReingestResponse, TraceOut
from app.workers.tasks import reindex_document_task

router = APIRouter(tags=["management"])

# Rough estimates for the trace view (we don't capture provider token usage).
_CHARS_PER_TOKEN = 4
_USD_PER_1K_TOKENS = 0.001


# --- Sources ---------------------------------------------------------------------


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(principal: CurrentPrincipal, db: DbSession) -> list[DocumentOut]:
    rows = await db.execute(
        select(Document, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(Document.tenant_id == principal.tenant_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    return [
        DocumentOut(
            id=doc.id,
            source_type=doc.source_type.value,
            uri=doc.uri,
            title=doc.title,
            status=doc.status.value,
            chunk_count=count,
            created_at=doc.created_at,
            last_modified=doc.last_modified,
        )
        for doc, count in rows.all()
    ]


@router.post(
    "/documents/{document_id}/reingest",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReingestResponse,
)
async def reingest_document(
    document_id: UUID, principal: NotDemoPrincipal, db: DbSession
) -> ReingestResponse:
    document = await db.get(Document, document_id)
    if document is None or document.tenant_id != principal.tenant_id:
        raise NotFoundError("Document not found")
    job = IngestionJob(document_id=document.id, state=IngestionState.QUEUED)
    db.add(job)
    await db.flush()
    document.status = DocumentStatus.PENDING
    await db.commit()
    reindex_document_task.delay(str(job.id), str(document.id))
    return ReingestResponse(job_id=job.id, document_id=document.id, state=job.state.value)


# --- Evaluations -----------------------------------------------------------------


@router.get("/eval-runs", response_model=list[EvalRunOut])
async def list_eval_runs(principal: CurrentPrincipal, db: DbSession) -> list[EvalRunOut]:
    runs = (
        await db.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(50))
    ).all()
    return [
        EvalRunOut(
            id=r.id,
            created_at=r.created_at,
            dataset=r.dataset,
            num_questions=r.num_questions,
            llm_model=r.llm_model,
            faithfulness=r.faithfulness,
            answer_relevancy=r.answer_relevancy,
            context_precision=r.context_precision,
            context_recall=r.context_recall,
        )
        for r in runs
    ]


# --- Traces ----------------------------------------------------------------------


@router.get("/traces", response_model=list[TraceOut])
async def list_traces(principal: CurrentPrincipal, db: DbSession) -> list[TraceOut]:
    messages = (
        await db.scalars(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == principal.tenant_id,
                Message.role == MessageRole.ASSISTANT,
            )
            .order_by(Message.created_at.desc())
            .limit(50)
        )
    ).all()
    traces = []
    for m in messages:
        est_tokens = max(1, len(m.content) // _CHARS_PER_TOKEN)
        traces.append(
            TraceOut(
                id=m.id,
                created_at=m.created_at,
                snippet=(m.content[:140] + "…") if len(m.content) > 140 else m.content,
                answer=m.content,
                latency_ms=m.latency_ms,
                grounding=m.grounding,
                self_corrected=m.self_corrected,
                used_web_search=m.used_web_search,
                citation_count=len(m.citations) if m.citations else 0,
                est_tokens=est_tokens,
                est_cost_usd=round(est_tokens / 1000 * _USD_PER_1K_TOKENS, 5),
            )
        )
    return traces
