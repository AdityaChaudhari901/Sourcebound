"""Langfuse observability setup.

Single place that initializes the Langfuse client from settings, verifies the
connection at startup, flushes on shutdown, and hands out a LangChain callback
handler for the (future) RAG graph.

Design notes / best practices applied:
- Tracing is **optional and non-fatal**: if keys are missing or the backend is
  unreachable, the app still runs — observability must never take down the API.
- Credentials are passed **explicitly** from validated settings (no reliance on
  the SDK silently reading the environment), so config is auditable.
- The LangChain integration is **lazy-imported** so the SDK isn't a hard import
  dependency until the RAG slice adds langchain.
- ``environment`` and ``release`` are set so traces are filterable by deploy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from langfuse import Langfuse

logger = get_logger(__name__)

_client: "Langfuse | None" = None


def configure_langfuse() -> "Langfuse | None":
    """Initialize the global Langfuse client. Returns ``None`` if not configured.

    Call once at startup. Safe to call again (returns the existing client).
    """
    global _client
    if _client is not None:
        return _client

    if not settings.langfuse_configured:
        logger.info("langfuse_disabled", reason="no_credentials_or_disabled")
        return None

    from langfuse import Langfuse  # imported after settings are loaded

    _client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),  # type: ignore[union-attr]
        host=settings.langfuse_host,
        environment=settings.environment,
        release=settings.langfuse_release,
    )

    # Verify connectivity without crashing the app if the backend is down.
    try:
        if _client.auth_check():
            logger.info("langfuse_ready", host=settings.langfuse_host, environment=settings.environment)
        else:
            logger.warning("langfuse_auth_failed", host=settings.langfuse_host)
    except Exception as exc:  # noqa: BLE001 - never fail startup on observability
        logger.warning("langfuse_auth_check_error", error=str(exc))

    return _client


def get_langfuse() -> "Langfuse | None":
    """Return the initialized Langfuse client, or ``None`` if tracing is off."""
    return _client


def shutdown_langfuse() -> None:
    """Flush any buffered events so nothing is lost on shutdown."""
    if _client is not None:
        _client.flush()
        logger.info("langfuse_flushed")


def get_langchain_handler(**kwargs: Any) -> Any | None:
    """Return a Langfuse LangChain ``CallbackHandler`` for the RAG graph.

    Lazy-imported so langchain isn't required until the RAG slice lands. Pass the
    handler in the chain/graph config: ``config={"callbacks": [handler]}`` and set
    trace attributes via metadata (``langfuse_session_id``, ``langfuse_user_id``,
    ``langfuse_tags``). Returns ``None`` when tracing is disabled.
    """
    if _client is None:
        return None
    from langfuse.langchain import CallbackHandler

    return CallbackHandler(**kwargs)
