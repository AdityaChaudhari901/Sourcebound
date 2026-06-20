"""Application settings, loaded and validated from the environment at startup.

Uses pydantic-settings so required values are validated once, fail fast on
startup, and are accessed everywhere through the cached ``settings`` singleton.
All runtime environment variables use the ``SOURCEBOUND_`` prefix to avoid
colliding with generic shell variables such as ``DEBUG`` or ``ENVIRONMENT``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SOURCEBOUND_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Sourcebound"
    app_version: str = "0.1.0"
    environment: Literal["local", "development", "staging", "production"] = "local"
    debug: bool = False

    # --- API ---
    api_v1_prefix: str = "/api/v1"

    # --- Database (async SQLAlchemy / asyncpg) ---
    # Standard DATABASE_URL name (unprefixed) so it matches docker-compose docs.
    database_url: str = Field(
        default="postgresql+asyncpg://sourcebound:sourcebound@localhost:5432/sourcebound",
        validation_alias=AliasChoices("DATABASE_URL", "SOURCEBOUND_DATABASE_URL"),
    )
    db_echo: bool = False

    # --- CORS (comma-separated string or list) ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Langfuse observability ---
    # These use the standard, unprefixed LANGFUSE_* env names (Langfuse convention)
    # rather than the SOURCEBOUND_ prefix, so they match the keys from the Langfuse
    # UI and the langfuse-cli. Tracing is a no-op when keys are absent.
    langfuse_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("LANGFUSE_ENABLED", "SOURCEBOUND_LANGFUSE_ENABLED"),
    )
    langfuse_public_key: str | None = Field(
        default=None, validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY")
    )
    langfuse_secret_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LANGFUSE_SECRET_KEY")
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )
    langfuse_release: str | None = Field(
        default=None, validation_alias=AliasChoices("LANGFUSE_RELEASE")
    )

    @property
    def langfuse_configured(self) -> bool:
        """True only when tracing is enabled and both keys are present."""
        return bool(
            self.langfuse_enabled and self.langfuse_public_key and self.langfuse_secret_key
        )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow SOURCEBOUND_CORS_ORIGINS to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (read from the environment once)."""
    return Settings()


settings = get_settings()
