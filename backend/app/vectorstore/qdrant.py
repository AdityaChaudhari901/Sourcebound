"""Qdrant client and collection helpers (synchronous).

The collection is created on demand with the embedding model's dimension and
cosine distance. Points carry a citation payload so a vector hit maps back to its
source: {document_id, chunk_id, heading_path, source_uri}. The point id is the
chunk's ``qdrant_point_id`` (a UUID) — the reverse link stored in Postgres.
"""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.core.config import settings


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    """Create the collection if it doesn't exist (cosine distance)."""
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        )


def upsert_points(
    client: QdrantClient, name: str, points: list[models.PointStruct]
) -> None:
    client.upsert(collection_name=name, points=points, wait=True)


def delete_points(client: QdrantClient, name: str, point_ids: list[str]) -> None:
    """Best-effort cleanup (e.g. if the DB commit fails after upsert)."""
    client.delete(
        collection_name=name,
        points_selector=models.PointIdsList(points=point_ids),
        wait=True,
    )
