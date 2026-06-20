"""Aggregates all v1 feature routers. Mounted under ``settings.api_v1_prefix``.

Feature routers (documents, query, ...) are included here as slices land.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import auth, feedback, ingest, query

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(ingest.router)
api_router.include_router(query.router)
api_router.include_router(feedback.router)
