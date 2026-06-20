"""POST /api/v1/query — naive RAG: retrieve, ground, generate, cite.

Thin router: validate the request, run the blocking query service in a worker
thread, shape the response.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.schemas.query import CitationOut, QueryRequest, QueryResponse
from app.services.query_service import answer_question

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    result = await run_in_threadpool(answer_question, request.question, k=request.k)
    return QueryResponse(
        answer=result.answer,
        citations=[
            CitationOut(
                source_uri=citation.source_uri,
                chunk_id=citation.chunk_id,
                snippet=citation.snippet,
            )
            for citation in result.citations
        ],
    )
