import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr
from schemasprint_api.config import Environment, LLMMode, Settings
from schemasprint_api.llm import (
    ChatMessage,
    GroqClient,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMUpstreamError,
)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": Environment.TEST,
        "database_dsn": SecretStr("postgresql://test/test"),
        "session_pepper": SecretStr("p" * 32),
        "csrf_key": SecretStr("c" * 32),
        "allowed_origin": "https://schemasprint.test",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_unconfigured_groq_never_sends_a_request() -> None:
    transport = httpx.MockTransport(
        lambda _: pytest.fail("unconfigured provider must not make HTTP calls")
    )
    async with httpx.AsyncClient(transport=transport) as http:
        client = GroqClient.from_settings(make_settings(), http_client=http)
        with pytest.raises(LLMUnavailableError, match="GROQ_UNAVAILABLE"):
            await client.complete([ChatMessage("user", "hello")])


@pytest.mark.asyncio
@respx.mock
async def test_groq_completion_is_typed_and_uses_server_side_credentials() -> None:
    route = respx.post("https://api.groq.test/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            headers={"x-request-id": "request-1"},
            json={
                "id": "chat-1",
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": "Done"}}],
            },
        )
    )
    settings = make_settings(
        groq_api_url="https://api.groq.test/openai/v1",
        groq_api_key=SecretStr("server-secret"),
        groq_model="test-model",
        llm_mode=LLMMode.GROQ,
    )
    async with httpx.AsyncClient() as http:
        client = GroqClient.from_settings(settings, http_client=http)
        result = await client.complete(
            [
                ChatMessage("system", "Return concise text."),
                ChatMessage("user", "hello"),
            ]
        )
    assert result.content == "Done"
    assert result.model == "test-model"
    assert result.provider_request_id == "request-1"
    assert route.called
    assert route.calls[0].request.headers["authorization"] == "Bearer server-secret"
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["max_tokens"] == 1024


@pytest.mark.asyncio
@respx.mock
async def test_groq_timeout_is_explicit() -> None:
    respx.post("https://api.groq.test/openai/v1/chat/completions").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )
    settings = make_settings(
        groq_api_url="https://api.groq.test/openai/v1",
        groq_api_key=SecretStr("server-secret"),
        llm_mode=LLMMode.GROQ,
    )
    async with httpx.AsyncClient() as http:
        client = GroqClient.from_settings(settings, http_client=http)
        with pytest.raises(LLMTimeoutError, match="GROQ_TIMEOUT"):
            await client.complete([ChatMessage("user", "hello")])


@pytest.mark.asyncio
@respx.mock
async def test_groq_rejects_provider_error_and_bounds_input() -> None:
    route = respx.post("https://api.groq.test/openai/v1/chat/completions").mock(
        return_value=httpx.Response(503, json={"error": "busy"})
    )
    settings = make_settings(
        groq_api_url="https://api.groq.test/openai/v1",
        groq_api_key=SecretStr("server-secret"),
        llm_mode=LLMMode.GROQ,
    )
    async with httpx.AsyncClient() as http:
        client = GroqClient.from_settings(settings, http_client=http)
        with pytest.raises(ValueError, match="character limit"):
            await client.complete([ChatMessage("user", "x" * (64 * 1024 + 1))])
        with pytest.raises(LLMUpstreamError, match="GROQ_UPSTREAM_ERROR"):
            await client.complete([ChatMessage("user", "hello")])
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [(429, LLMRateLimitError), (503, LLMUpstreamError)],
)
async def test_groq_classifies_retryable_provider_errors(
    status_code: int, error_type: type[LLMProviderError]
) -> None:
    headers = {"retry-after": "12"} if status_code == 429 else {}
    respx.post("https://api.groq.test/openai/v1/chat/completions").mock(
        return_value=httpx.Response(status_code, headers=headers, json={})
    )
    settings = make_settings(
        groq_api_url="https://api.groq.test/openai/v1",
        groq_api_key=SecretStr("server-secret"),
        llm_mode=LLMMode.GROQ,
    )
    async with httpx.AsyncClient() as http:
        client = GroqClient.from_settings(settings, http_client=http)
        with pytest.raises(error_type) as raised:
            await client.complete([ChatMessage("user", "hello")])
    assert raised.value.retryable
    if isinstance(raised.value, LLMRateLimitError):
        assert raised.value.retry_after_seconds == 12


def test_groq_settings_validate_timeout_and_production_transport_security() -> None:
    with pytest.raises(ValueError, match="Groq timeout"):
        make_settings(groq_timeout_seconds=0)
    with pytest.raises(ValueError, match="HTTPS"):
        make_settings(
            environment=Environment.PRODUCTION,
            allowed_origin="https://schemasprint.example",
            groq_api_url="http://groq.internal",
            groq_api_key=SecretStr("server-secret"),
        )


def test_groq_mode_requires_key_and_stub_is_non_production() -> None:
    with pytest.raises(ValueError, match="requires an API key"):
        make_settings(llm_mode=LLMMode.GROQ)
    with pytest.raises(ValueError, match="development and test"):
        make_settings(environment=Environment.PRODUCTION, llm_mode=LLMMode.STUB)
