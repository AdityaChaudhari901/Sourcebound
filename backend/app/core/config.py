"""Application settings, loaded and validated from the environment at startup.

Uses pydantic-settings so required values are validated once, fail fast on
startup, and are accessed everywhere through the cached ``settings`` singleton.
All runtime environment variables use the ``SOURCEBOUND_`` prefix to avoid
colliding with generic shell variables such as ``DEBUG`` or ``ENVIRONMENT``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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

    # --- CORS (comma-separated string or list) ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

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
