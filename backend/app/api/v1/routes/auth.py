"""Auth endpoints: signup/login (JWT) and API-key management (programmatic)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentPrincipal
from app.database.models import Tenant
from app.database.session import DbSession
from app.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyOut,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
    WorkspaceOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def signup(payload: SignupRequest, db: DbSession) -> TokenResponse:
    user = await auth_service.signup(db, email=payload.email, password=payload.password)
    return TokenResponse(access_token=auth_service.issue_token(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = await auth_service.authenticate(db, email=payload.email, password=payload.password)
    return TokenResponse(access_token=auth_service.issue_token(user))


@router.get("/me", response_model=UserOut)
async def me(principal: CurrentPrincipal, db: DbSession) -> UserOut:
    tenant = await db.get(Tenant, principal.tenant_id)
    return UserOut(
        id=principal.user_id,
        email=principal.email,
        tenant_id=principal.tenant_id,
        workspace=WorkspaceOut(id=tenant.id, name=tenant.name),
    )


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def workspaces(principal: CurrentPrincipal, db: DbSession) -> list[WorkspaceOut]:
    # One workspace per user for now; this is the seam for multi-membership later.
    tenant = await db.get(Tenant, principal.tenant_id)
    return [WorkspaceOut(id=tenant.id, name=tenant.name)]


@router.post(
    "/api-keys", status_code=status.HTTP_201_CREATED, response_model=ApiKeyCreatedResponse
)
async def create_api_key(
    payload: ApiKeyCreateRequest, principal: CurrentPrincipal, db: DbSession
) -> ApiKeyCreatedResponse:
    api_key, full_key = await auth_service.create_api_key(
        db, user_id=principal.user_id, name=payload.name
    )
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        api_key=full_key,  # shown ONCE
    )


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(principal: CurrentPrincipal, db: DbSession) -> list[ApiKeyOut]:
    keys = await auth_service.list_api_keys(db, user_id=principal.user_id)
    return [
        ApiKeyOut(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: UUID, principal: CurrentPrincipal, db: DbSession):
    await auth_service.revoke_api_key(db, user_id=principal.user_id, key_id=key_id)
    return None
