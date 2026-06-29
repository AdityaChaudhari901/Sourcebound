"""Auth dependencies. Default-closed: a route that depends on CurrentPrincipal is
protected, and the principal is resolved from EITHER a JWT Bearer token (interactive
clients) OR an X-API-Key header (programmatic clients)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import Principal, decode_access_token, hash_api_key
from app.database.models import ApiKey, User
from app.services.demo_service import DEMO_EMAIL
from app.database.session import DbSession


async def get_current_principal(
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    # 1) JWT Bearer (browser/frontend).
    if authorization and authorization.lower().startswith("bearer "):
        payload = decode_access_token(authorization[7:].strip())
        try:
            user_id = uuid.UUID(payload.get("sub", ""))
        except ValueError as exc:
            raise UnauthorizedError("Invalid token subject") from exc
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account not found or disabled")
        return Principal(
            user_id=user.id, tenant_id=user.tenant_id, email=user.email, auth_method="jwt"
        )

    # 2) API key (programmatic). Look up by sha256 hash; reject revoked keys.
    if x_api_key:
        api_key = await db.scalar(
            select(ApiKey).where(
                ApiKey.key_hash == hash_api_key(x_api_key),
                ApiKey.revoked_at.is_(None),
            )
        )
        if api_key is None:
            raise UnauthorizedError("Invalid API key")
        user = await db.get(User, api_key.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account not found or disabled")
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return Principal(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            auth_method="api_key",
            api_key_id=api_key.id,
        )

    raise UnauthorizedError("Authentication required")


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


async def forbid_demo(principal: CurrentPrincipal) -> Principal:
    """Block mutations for the shared demo workspace (it's read-only)."""
    if principal.email == DEMO_EMAIL:
        raise ForbiddenError(
            "The demo workspace is read-only. Sign up to ingest and manage your own sources."
        )
    return principal


# Use on write endpoints (ingest, delete, settings) to keep the demo read-only.
NotDemoPrincipal = Annotated[Principal, Depends(forbid_demo)]
