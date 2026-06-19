"""Aggregates all v1 feature routers. Mounted under ``settings.api_v1_prefix``.

Feature routers (documents, query, ...) are included here as slices land.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()

# Feature routers will be registered here, e.g.:
# from app.api.v1.routes import documents
# api_router.include_router(documents.router)
