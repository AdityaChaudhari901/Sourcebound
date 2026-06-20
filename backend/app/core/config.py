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

    # --- Auth (JWT + API keys) ---
    jwt_secret: SecretStr = Field(
        default=SecretStr("dev-insecure-change-me-in-production"),
        validation_alias=AliasChoices("JWT_SECRET", "SOURCEBOUND_JWT_SECRET"),
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 720  # 12h (dev convenience)
    api_key_prefix: str = "sb_"  # human-readable prefix on generated API keys

    # --- Database (async SQLAlchemy / asyncpg) ---
    # Standard DATABASE_URL name (unprefixed) so it matches docker-compose docs.
    database_url: str = Field(
        default="postgresql+asyncpg://sourcebound:sourcebound@localhost:5432/sourcebound",
        validation_alias=AliasChoices("DATABASE_URL", "SOURCEBOUND_DATABASE_URL"),
    )
    db_echo: bool = False

    @property
    def sync_database_url(self) -> str:
        """The sync (psycopg) form of database_url, for the synchronous ingestion path."""
        return self.database_url.replace("+asyncpg", "+psycopg")

    # --- Redis (Celery broker + result backend) ---
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "SOURCEBOUND_REDIS_URL"),
    )

    # --- Vector store (Qdrant) ---
    qdrant_url: str = Field(
        default="http://localhost:6333",
        validation_alias=AliasChoices("QDRANT_URL", "SOURCEBOUND_QDRANT_URL"),
    )
    qdrant_collection: str = Field(
        default="sourcebound_chunks",
        validation_alias=AliasChoices("QDRANT_COLLECTION", "SOURCEBOUND_QDRANT_COLLECTION"),
    )

    # --- Embeddings ---
    embedding_provider: str = "fastembed"  # interface key; only "fastembed" wired for now
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # open BGE, 384-dim
    sparse_embedding_model: str = "Qdrant/bm25"  # BM25 sparse vectors (lexical)

    # --- Retrieval mode + hybrid fusion (weighted Reciprocal Rank Fusion) ---
    retriever_mode: str = "hybrid"        # hybrid | dense | sparse
    hybrid_dense_weight: float = 1.0      # weight on dense (semantic) ranking in RRF
    hybrid_sparse_weight: float = 1.0     # weight on sparse (BM25/lexical) ranking in RRF
    hybrid_rrf_k: int = 60                # RRF rank constant (standard default)
    hybrid_prefetch_limit: int = 20       # candidates pulled from each retriever before fusing

    # --- Chunking (tune against an eval set later) ---
    chunk_size: int = 1000      # characters (~250 tokens at ~4 chars/token)
    chunk_overlap: int = 150    # ~15% of chunk_size, preserves context across boundaries

    # --- Retrieval + rerank (two-stage: retrieve N -> rerank to k) ---
    retrieve_top_n: int = 20    # stage-1 candidates from hybrid retrieval (N)
    query_top_k: int = 5        # stage-2 results after rerank, passed to the LLM (k)
    rerank_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-base"  # BGE cross-encoder

    # --- Corrective loop ---
    max_query_retries: int = 2  # max query rewrites before degrading gracefully

    # --- Web search fallback (Tavily; off unless enabled + key present) ---
    web_search_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("WEB_SEARCH_ENABLED", "SOURCEBOUND_WEB_SEARCH_ENABLED"),
    )
    web_search_provider: str = "tavily"
    web_search_max_results: int = 4
    tavily_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("TAVILY_API_KEY")
    )

    @property
    def web_search_configured(self) -> bool:
        """True only when web fallback is enabled AND a key is present."""
        return bool(self.web_search_enabled and self.tavily_api_key)

    # --- LLM (swappable provider interface; default free local Ollama) ---
    llm_provider: str = "ollama"   # ollama | groq | gemini | openai | vertex
    llm_model: str | None = None   # None -> provider default
    llm_temperature: float = 0.0   # deterministic; low temp curbs fabrication
    llm_base_url: str | None = None  # override the provider's default base URL
    ollama_base_url: str = "http://localhost:11434/v1"

    # Vertex AI (uses Application Default Credentials; bills GCP project credits)
    vertex_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VERTEX_PROJECT_ID", "GOOGLE_CLOUD_PROJECT"),
    )
    vertex_region: str = Field(
        default="us-east5",
        validation_alias=AliasChoices("VERTEX_REGION", "GOOGLE_CLOUD_LOCATION"),
    )
    groq_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY")
    )
    google_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY")
    )
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY")
    )

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
