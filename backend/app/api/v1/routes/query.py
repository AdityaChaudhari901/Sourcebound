"""Query endpoints — naive RAG: retrieve -> rerank -> ground -> generate -> cite.

- POST /api/v1/query         : non-streaming, returns the full answer + citations.
- POST /api/v1/query/stream  : Server-Sent Events — streams answer tokens, then a
  final event with the citations.

Thin routers: run the blocking service in a worker thread (non-streaming) or as a
threadpool-iterated generator (streaming), and shape the output.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.schemas.query import CitationOut, QueryRequest, QueryResponse
from app.services.query_service import (
    FinalResult,
    TokenChunk,
    answer_question,
    stream_answer,
)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    result = await run_in_threadpool(answer_question, request.question, k=request.k)
    return QueryResponse(
        answer=result.answer,
        citations=[
            CitationOut(
                source_uri=c.source_uri,
                chunk_id=c.chunk_id,
                snippet=c.snippet,
                external=c.external,
            )
            for c in result.citations
        ],
    )


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    def event_stream() -> Iterator[str]:
        try:
            for event in stream_answer(request.question, k=request.k):
                if isinstance(event, TokenChunk):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, FinalResult):
                    yield _sse(
                        "citations",
                        {
                            "answer": event.answer,
                            "citations": [
                                {
                                    "source_uri": c.source_uri,
                                    "chunk_id": c.chunk_id,
                                    "snippet": c.snippet,
                                    "external": c.external,
                                }
                                for c in event.citations
                            ],
                        },
                    )
            yield _sse("done", {})
        except Exception as exc:  # noqa: BLE001 - headers are already sent; report via SSE
            yield _sse("error", {"message": str(exc)})

    # A sync generator is iterated in a threadpool by Starlette, so it won't block the loop.
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so tokens flush live
        },
    )
