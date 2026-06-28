"""Unit tests for production-hardening: fail-fast secret validation, the rate-limit
identity key, and security response headers."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings


def _settings(monkeypatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_local_allows_insecure_defaults(monkeypatch):
    # environment defaults to "local" -> validator is a no-op, defaults are fine.
    s = _settings(monkeypatch, SOURCEBOUND_ENVIRONMENT="local")
    assert s.environment == "local"


def test_production_rejects_insecure_jwt(monkeypatch):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _settings(
            monkeypatch,
            SOURCEBOUND_ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://u:strongpass@db:5432/app",
        )


def test_production_rejects_wildcard_cors(monkeypatch):
    with pytest.raises(ValidationError, match="CORS"):
        _settings(
            monkeypatch,
            SOURCEBOUND_ENVIRONMENT="production",
            JWT_SECRET="a-strong-secret",
            DATABASE_URL="postgresql+asyncpg://u:strongpass@db:5432/app",
            SOURCEBOUND_CORS_ORIGINS="*",
        )


def test_production_rejects_default_db_credentials(monkeypatch):
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        _settings(
            monkeypatch,
            SOURCEBOUND_ENVIRONMENT="production",
            JWT_SECRET="a-strong-secret",
            # default sourcebound:sourcebound credentials
            DATABASE_URL="postgresql+asyncpg://sourcebound:sourcebound@db:5432/app",
        )


def test_production_accepts_strong_config(monkeypatch):
    s = _settings(
        monkeypatch,
        SOURCEBOUND_ENVIRONMENT="production",
        JWT_SECRET="a-strong-secret",
        DATABASE_URL="postgresql+asyncpg://u:strongpass@db:5432/app",
        SOURCEBOUND_CORS_ORIGINS="https://app.example.com",
    )
    assert s.environment == "production"
    assert s.cors_origins == ["https://app.example.com"]


def test_client_identity_prefers_token_then_ip():
    from starlette.requests import Request

    from app.core.middleware import _client_identity

    def make(headers: dict[str, str], client_host: str | None = "1.2.3.4") -> Request:
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (client_host, 0) if client_host else None,
        }
        return Request(scope)

    tok = _client_identity(make({"authorization": "Bearer abc"}))
    assert tok.startswith("tok:")
    # same token -> same bucket; different token -> different bucket
    assert tok == _client_identity(make({"authorization": "Bearer abc"}))
    assert tok != _client_identity(make({"authorization": "Bearer xyz"}))
    # anonymous -> IP bucket, honoring X-Forwarded-For
    assert _client_identity(make({"x-forwarded-for": "9.9.9.9, 10.0.0.1"})) == "ip:9.9.9.9"
    assert _client_identity(make({})) == "ip:1.2.3.4"


def test_security_headers_on_liveness_probe():
    # /health needs no dependencies and is rate-limit-exempt -> hermetic.
    from app.main import create_app

    with TestClient(create_app()) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
