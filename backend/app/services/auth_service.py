"""Auth business logic (thick service): signup, login, API-key issue/list/revoke.

Returns/raises domain types; the router maps them to HTTP. No secret is ever
logged here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import (
    GeneratedApiKey,
    create_access_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from app.database.models import ApiKey, User


async def signup(db: AsyncSession, *, email: str, password: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("An account with that email already exists.")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    # Verify even when the user is missing is unnecessary here; a generic 401 avoids
    # leaking which emails exist.
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled.")
    return user


def issue_token(user: User) -> str:
    return create_access_token(str(user.id))


async def create_api_key(db: AsyncSession, *, user_id: uuid.UUID, name: str) -> tuple[ApiKey, str]:
    generated: GeneratedApiKey = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        name=name,
        prefix=generated.prefix,
        key_hash=generated.key_hash,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, generated.full_key  # full key returned to caller once, never stored


async def list_api_keys(db: AsyncSession, *, user_id: uuid.UUID) -> list[ApiKey]:
    result = await db.scalars(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return list(result)


async def revoke_api_key(db: AsyncSession, *, user_id: uuid.UUID, key_id: uuid.UUID) -> None:
    api_key = await db.get(ApiKey, key_id)
    if api_key is None or api_key.user_id != user_id:
        raise NotFoundError("API key not found.")
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(timezone.utc)
        await db.commit()
