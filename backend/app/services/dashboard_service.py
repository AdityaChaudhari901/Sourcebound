"""Dashboard aggregations — all tenant-scoped (except the global eval scorecard).

One read per tile, assembled into a single payload the frontend renders as bento
tiles. Kept as cheap COUNT/aggregate queries against existing tables.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Chunk,
    Conversation,
    Document,
    DocumentStatus,
    EvalRun,
    IngestionJob,
    Message,
    MessageRole,
)

# Rough per-answer cost estimate (Gemini flash-class), for the "est. cost" stat.
_EST_COST_PER_ANSWER_USD = 0.0015


async def build_dashboard(db: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    # --- Source coverage ---
    documents = await db.scalar(
        select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id)
    )
    chunks = await db.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.tenant_id == tenant_id)
    )
    last_sync = await db.scalar(
        select(func.max(Document.created_at)).where(Document.tenant_id == tenant_id)
    )
    ready = await db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.tenant_id == tenant_id, Document.status == DocumentStatus.READY)
    )

    # --- Answer quality (latest eval run; pipeline-level, not per-tenant) ---
    eval_run = await db.scalar(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(1))
    answer_quality = (
        {
            "faithfulness": eval_run.faithfulness,
            "answer_relevancy": eval_run.answer_relevancy,
            "context_precision": eval_run.context_precision,
            "context_recall": eval_run.context_recall,
            "dataset": eval_run.dataset,
            "created_at": eval_run.created_at.isoformat(),
        }
        if eval_run is not None
        else None
    )

    # --- Recent answers ---
    recent_rows = (
        await db.scalars(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.tenant_id == tenant_id, Message.role == MessageRole.ASSISTANT)
            .order_by(Message.created_at.desc())
            .limit(6)
        )
    ).all()
    recent_answers = [
        {
            "id": str(m.id),
            "snippet": (m.content[:120] + "…") if len(m.content) > 120 else m.content,
            "citation_count": len(m.citations) if m.citations else 0,
            "created_at": m.created_at.isoformat(),
        }
        for m in recent_rows
    ]

    # --- Ingestion status (jobs by state, for this tenant's documents) ---
    job_rows = await db.execute(
        select(IngestionJob.state, func.count())
        .join(Document, IngestionJob.document_id == Document.id)
        .where(Document.tenant_id == tenant_id)
        .group_by(IngestionJob.state)
    )
    state_counts = {state.value: count for state, count in job_rows.all()}
    ingestion_status = {
        "queued": state_counts.get("queued", 0),
        "running": state_counts.get("running", 0),
        "succeeded": state_counts.get("succeeded", 0),
        "failed": state_counts.get("failed", 0),
    }

    # --- Latency & cost (recent answer wall times) ---
    latency_rows = (
        await db.scalars(
            select(Message.latency_ms)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == tenant_id,
                Message.role == MessageRole.ASSISTANT,
                Message.latency_ms.is_not(None),
            )
            .order_by(Message.created_at.desc())
            .limit(20)
        )
    ).all()
    latencies = [int(x) for x in latency_rows][::-1]  # chronological
    answers_total = await db.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.tenant_id == tenant_id, Message.role == MessageRole.ASSISTANT)
    )
    avg_ms = round(sum(latencies) / len(latencies)) if latencies else None
    p95_ms = sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else None

    return {
        "source_coverage": {
            "documents": documents or 0,
            "chunks": chunks or 0,
            "ready": ready or 0,
            "last_sync": last_sync.isoformat() if last_sync else None,
        },
        "answer_quality": answer_quality,
        "recent_answers": recent_answers,
        "ingestion_status": ingestion_status,
        "latency": {
            "recent_ms": latencies,
            "avg_ms": avg_ms,
            "p95_ms": p95_ms,
            "answers_total": answers_total or 0,
            "est_cost_usd": round((answers_total or 0) * _EST_COST_PER_ANSWER_USD, 4),
        },
    }
