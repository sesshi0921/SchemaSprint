"""Bounded LLM provider boundary.

This module owns the server-side Groq credential and speaks only the
OpenAI-compatible chat-completions protocol.  It intentionally has no route
registration and no frontend-facing types.  Callers must handle
``LLMUnavailableError`` rather than substituting generated or canned content.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Self

import httpx

from .config import LLMMode, Settings

MessageRole = Literal["system", "user", "assistant"]
MAX_INPUT_CHARACTERS = 64 * 1024
MAX_OUTPUT_CHARACTERS = 128 * 1024
MAX_OUTPUT_TOKENS = 4096
MAX_RESPONSE_BYTES = 1024 * 1024


class LLMError(Exception):
    """Base error for provider failures that callers may expose safely."""


class LLMUnavailableError(LLMError):
    """The provider is not configured or returned an unusable response."""


class LLMTimeoutError(LLMError):
    """The provider did not respond before the configured deadline."""


class LLMProviderError(LLMError):
    """The provider returned an error or the transport failed."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class LLMRateLimitError(LLMProviderError):
    """The provider rejected the request due to rate limiting."""

    def __init__(self, retry_after_seconds: int | None) -> None:
        super().__init__(
            "GROQ_RATE_LIMITED",
            status_code=429,
            retryable=True,
        )
        self.retry_after_seconds = retry_after_seconds


class LLMUpstreamError(LLMProviderError):
    """The provider returned a retryable 5xx response."""

    def __init__(self, status_code: int) -> None:
        super().__init__(
            "GROQ_UPSTREAM_ERROR",
            status_code=status_code,
            retryable=True,
        )


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class ChatCompletion:
    content: str
    model: str
    provider_request_id: str | None


class GroqClient:
    """Minimal, bounded, injectable async Groq adapter.

    The HTTP client can be injected for tests.  A client created from settings
    owns its ``httpx.AsyncClient`` and should be used as an async context
    manager, or closed explicitly.
    """

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        enabled: bool = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_url = api_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._enabled = enabled
        self._http = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_http = http_client is None

    @classmethod
    def from_settings(
        cls, settings: Settings, *, http_client: httpx.AsyncClient | None = None
    ) -> Self:
        key = (
            settings.groq_api_key.get_secret_value()
            if settings.groq_api_key is not None
            else None
        )
        return cls(
            api_url=str(settings.groq_api_url),
            api_key=key,
            model=settings.groq_model,
            timeout_seconds=settings.groq_timeout_seconds,
            enabled=settings.llm_mode is LLMMode.GROQ,
            http_client=http_client,
        )

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._api_key and self._api_key.strip())

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_output_tokens: int = 1024,
    ) -> ChatCompletion:
        """Generate bounded text without exposing provider details to callers."""
        if not self.configured:
            raise LLMUnavailableError("GROQ_UNAVAILABLE")
        if not messages or len(messages) > 32:
            raise ValueError("messages must contain between 1 and 32 items")
        input_characters = sum(len(message.content) for message in messages)
        if input_characters > MAX_INPUT_CHARACTERS:
            raise ValueError("LLM input exceeds the configured character limit")
        if not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
            raise ValueError("LLM output token limit is invalid")
        if any(not message.content.strip() for message in messages):
            raise ValueError("LLM messages cannot be empty")

        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "max_tokens": max_output_tokens,
            "temperature": 0,
        }
        try:
            response = await self._http.post(
                self._api_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("GROQ_TIMEOUT") from error
        except httpx.HTTPError as error:
            raise LLMProviderError("GROQ_TRANSPORT_ERROR") from error

        if len(response.content) > MAX_RESPONSE_BYTES:
            raise LLMProviderError("GROQ_RESPONSE_TOO_LARGE")
        if response.status_code == 429:
            retry_after: int | None = None
            raw_retry_after = response.headers.get("retry-after")
            if raw_retry_after is not None:
                try:
                    candidate = int(raw_retry_after)
                except ValueError:
                    candidate = -1
                if 0 <= candidate <= 3600:
                    retry_after = candidate
            raise LLMRateLimitError(retry_after)
        if response.status_code >= 500:
            raise LLMUpstreamError(response.status_code)
        if response.status_code >= 400:
            raise LLMProviderError(
                f"GROQ_HTTP_{response.status_code}",
                status_code=response.status_code,
            )
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            model = data.get("model", self._model)
            request_id = response.headers.get("x-request-id")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMUnavailableError("GROQ_INVALID_RESPONSE") from error
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailableError("GROQ_EMPTY_RESPONSE")
        if not isinstance(model, str) or len(content) > MAX_OUTPUT_CHARACTERS:
            raise LLMProviderError("GROQ_OUTPUT_TOO_LARGE")
        return ChatCompletion(content, model, request_id)
