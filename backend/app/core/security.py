"""Auth primitives: password hashing, JWT, API-key generation/hashing, Principal.

Secret handling rules baked in here:
- Passwords are hashed with **argon2** (slow, salted) — never stored or logged in
  the clear.
- API keys are random high-entropy tokens; we store only their **sha256** (fast,
  so we can look them up by hash) and a non-secret display prefix. The full key is
  shown to the user exactly once, at creation.
- The JWT signing secret comes from config (SecretStr) and is never logged.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.errors import UnauthorizedError

_password_hasher = PasswordHasher()


# --- Passwords -------------------------------------------------------------------


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# --- JWT -------------------------------------------------------------------------


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


# --- API keys --------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedApiKey:
    full_key: str  # shown to the user ONCE
    prefix: str    # stored + displayed (non-secret)
    key_hash: str  # stored (sha256 hex)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_api_key() -> GeneratedApiKey:
    full_key = settings.api_key_prefix + secrets.token_urlsafe(32)
    return GeneratedApiKey(
        full_key=full_key,
        prefix=full_key[: len(settings.api_key_prefix) + 6],
        key_hash=hash_api_key(full_key),
    )


# --- Principal -------------------------------------------------------------------


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    auth_method: Literal["jwt", "api_key"]
    api_key_id: uuid.UUID | None = None
