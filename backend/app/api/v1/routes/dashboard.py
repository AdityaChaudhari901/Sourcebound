"""Dashboard endpoint — one tenant-scoped aggregate payload for the bento grid."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentPrincipal
from app.database.session import DbSession
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(principal: CurrentPrincipal, db: DbSession) -> dict[str, Any]:
    return await dashboard_service.build_dashboard(db, tenant_id=principal.tenant_id)
