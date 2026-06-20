"""Auth request/response schemas. Plaintext secrets only ever appear inbound
(signup/login) or once outbound (the full API key at creation) — never stored."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str  # non-secret display value
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyCreatedResponse(ApiKeyOut):
    api_key: str = Field(..., description="The full key — shown ONCE. Store it now.")
