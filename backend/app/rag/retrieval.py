"""Dense top-k retrieval from Qdrant.

Embeds the question with the same model used at ingestion (BGE) and runs a
similarity search. Returns chunks with their text and citation metadata from the
point payload. Naive RAG for now — no reranking or query rewriting yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.rag.providers.embeddings import get_embedding_provider
from app.vectorstore.qdrant import get_qdrant_client


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    source_uri: str
    heading_path: str | None
    text: str
    score: float


def retrieve(question: str, *, k: int | None = None) -> list[RetrievedChunk]:
    top_k = k or settings.query_top_k
    embedder = get_embedding_provider()
    client = get_qdrant_client()

    query_vector = embedder.embed_query(question)
    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    results: list[RetrievedChunk] = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            RetrievedChunk(
                chunk_id=payload.get("chunk_id", str(point.id)),
                document_id=payload.get("document_id", ""),
                source_uri=payload.get("source_uri", "unknown"),
                heading_path=payload.get("heading_path"),
                text=payload.get("text", ""),
                score=point.score,
            )
        )
    return results
