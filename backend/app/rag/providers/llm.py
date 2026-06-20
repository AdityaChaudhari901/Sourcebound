"""LLM provider interface and a unified OpenAI-compatible implementation.

Services depend on the ``LLMProvider`` protocol, never a concrete SDK. Groq,
Gemini, Ollama, and OpenAI all expose OpenAI-compatible chat APIs, so one client
(pointed at different base URLs/keys) covers them; switching is a config change.

Default: Ollama (local, free, no key). Set ``LLM_PROVIDER=groq`` + ``GROQ_API_KEY``
(or ``gemini`` + ``GOOGLE_API_KEY``) to use a hosted free tier instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import settings
from app.core.errors import AppError


class LLMConfigError(AppError):
    code, status_code = "llm_not_configured", 503


class LLMRequestError(AppError):
    code, status_code = "llm_request_failed", 502


@runtime_checkable
class LLMProvider(Protocol):
    model_name: str

    def complete(self, *, system: str, user: str) -> str:
        """Return the model's text completion for a system + user prompt."""
        ...


@dataclass(frozen=True)
class _ProviderPreset:
    base_url: str
    api_key: str | None
    default_model: str


def _resolve_preset() -> _ProviderPreset:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return _ProviderPreset(
            base_url=settings.llm_base_url or settings.ollama_base_url,
            api_key="ollama",  # Ollama ignores the key but the client requires one
            default_model="qwen2.5:0.5b",
        )
    if provider == "groq":
        key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else None
        return _ProviderPreset(
            base_url=settings.llm_base_url or "https://api.groq.com/openai/v1",
            api_key=key,
            default_model="llama-3.1-8b-instant",
        )
    if provider == "gemini":
        key = settings.google_api_key.get_secret_value() if settings.google_api_key else None
        return _ProviderPreset(
            base_url=settings.llm_base_url
            or "https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=key,
            default_model="gemini-2.0-flash",
        )
    if provider == "openai":
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        return _ProviderPreset(
            base_url=settings.llm_base_url or "https://api.openai.com/v1",
            api_key=key,
            default_model="gpt-4o-mini",
        )
    raise LLMConfigError(f"Unknown LLM provider: {settings.llm_provider!r}")


class OpenAICompatibleProvider:
    def __init__(self, preset: _ProviderPreset) -> None:
        from openai import OpenAI

        if not preset.api_key:
            raise LLMConfigError(
                f"No API key for LLM provider {settings.llm_provider!r}; set the relevant key."
            )
        self.model_name = settings.llm_model or preset.default_model
        self._client = OpenAI(base_url=preset.base_url, api_key=preset.api_key)

    def complete(self, *, system: str, user: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                temperature=settings.llm_temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - surface upstream failures cleanly
            raise LLMRequestError(f"LLM request failed: {exc}") from exc
        return (response.choices[0].message.content or "").strip()


class VertexProvider:
    """Gemini on Vertex AI via google-genai. Auth is ADC; usage bills GCP credits."""

    def __init__(self) -> None:
        from google import genai

        if not settings.vertex_project:
            raise LLMConfigError("VERTEX_PROJECT_ID is not set for the vertex provider.")
        self.model_name = settings.llm_model or "gemini-2.5-flash"
        self._client = genai.Client(
            vertexai=True,
            project=settings.vertex_project,
            location=settings.vertex_region,
        )

    def complete(self, *, system: str, user: str) -> str:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=settings.llm_temperature,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMRequestError(f"Vertex request failed: {exc}") from exc
        return (response.text or "").strip()


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    if settings.llm_provider.lower() == "vertex":
        return VertexProvider()
    return OpenAICompatibleProvider(_resolve_preset())
