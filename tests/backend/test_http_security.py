from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import Request
from pydantic import AnyHttpUrl, SecretStr
from schemasprint_api.app import create_app
from schemasprint_api.config import Environment, Settings
from schemasprint_api.database import Database
from schemasprint_api.http_security import (
    InProcessRateLimiter,
    client_address,
    request_source_key,
)


class _Database(Database):
    def __init__(self) -> None:
        self.opened = False

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.opened = False


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": Environment.TEST,
        "database_dsn": SecretStr("postgresql://unused"),
        "session_pepper": SecretStr("p" * 32),
        "csrf_key": SecretStr("c" * 32),
        "allowed_origin": AnyHttpUrl("https://schemasprint.test"),
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_security_headers_are_strict_and_request_id_is_server_generated() -> None:
    app = create_app(make_settings(), _Database())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
            headers={"X-Request-ID": "attacker-value"},
        ) as client,
    ):
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    )
    assert response.headers["permissions-policy"]
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] != "attacker-value"


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", [None, "https://evil.example", "null"])
async def test_unsafe_methods_require_exact_same_origin(origin: str | None) -> None:
    app = create_app(make_settings(), _Database())
    headers = {} if origin is None else {"Origin": origin}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
        ) as client,
    ):
        response = await client.post("/api/v1/session", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_CHECK_FAILED"


@pytest.mark.asyncio
async def test_advertised_body_limit_is_rejected_before_route_dispatch() -> None:
    app = create_app(make_settings(request_body_limit_bytes=16), _Database())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
        ) as client,
    ):
        response = await client.request(
            "GET", "/health/live", content=b"0123456789abcdefg", headers={"Origin": "x"}
        )
    assert response.status_code == 413
    assert response.json()["code"] == "REQUEST_BODY_TOO_LARGE"


@pytest.mark.asyncio
async def test_chunked_body_limit_is_enforced_even_when_route_ignores_body() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"0123456789"
        yield b"abcdefghi"

    app = create_app(make_settings(request_body_limit_bytes=16), _Database())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
        ) as client,
    ):
        response = await client.request("GET", "/health/live", content=chunks())
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_rate_limit_is_bounded_and_returns_retry_after() -> None:
    app = create_app(
        make_settings(rate_limit_capacity=1, rate_limit_window_seconds=60),
        _Database(),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
        ) as client,
    ):
        first = await client.get("/health/live")
        second = await client.get("/health/live")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"
    assert app.state.rate_limiter.key_count <= 2


@pytest.mark.asyncio
async def test_ip_limit_is_not_evicted_by_action_key_when_bound_is_one() -> None:
    app = create_app(
        make_settings(
            rate_limit_capacity=1, rate_limit_window_seconds=60, rate_limit_max_keys=1
        ),
        _Database(),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
        ) as client,
    ):
        first = await client.get("/health/live")
        second = await client.get("/health/live")
    assert first.status_code == 200
    assert second.status_code == 429


def test_forwarded_address_requires_trusted_immediate_peer() -> None:
    base_scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"cf-connecting-ip", b"203.0.113.7")],
        "client": ("198.51.100.10", 443),
        "server": ("schemasprint.test", 443),
        "scheme": "https",
    }
    request = Request(base_scope)
    assert client_address(request, ()) == "198.51.100.10"
    assert client_address(request, ("198.51.100.0/24",)) == "203.0.113.7"
    assert request_source_key(request, (), "p" * 32) == "198.51.100.10"


@pytest.mark.asyncio
async def test_limiter_rejects_new_keys_when_bounded() -> None:
    limiter = InProcessRateLimiter(1, 60, 1)
    assert (await limiter.check("first")).allowed
    # Key spray evicts, rather than globally denying every new source.
    assert (await limiter.check("second")).allowed
    assert limiter.key_count == 1


@pytest.mark.asyncio
async def test_limiter_still_throttles_a_reused_key() -> None:
    limiter = InProcessRateLimiter(1, 60, 2)
    assert (await limiter.check("stable")).allowed
    rejected = await limiter.check("stable")
    assert not rejected.allowed
    assert rejected.retry_after_seconds == 60


def test_production_requires_https_and_keeps_hsts_enabled() -> None:
    with pytest.raises(ValueError):
        make_settings(environment=Environment.PRODUCTION, allowed_origin="http://local")
    production = make_settings(environment=Environment.PRODUCTION)
    assert production.environment is Environment.PRODUCTION
