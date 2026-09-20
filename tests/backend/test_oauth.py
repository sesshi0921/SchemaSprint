from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import AnyHttpUrl, SecretStr
from schemasprint_api.config import Environment, Settings
from schemasprint_api.oauth import (
    OAuthIdentity,
    authorization_url,
    decrypt_verifier,
    exchange_and_fetch,
    new_attempt,
)


def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        environment=Environment.TEST,
        database_dsn=SecretStr("postgresql://unused"),
        session_pepper=SecretStr("p" * 32),
        csrf_key=SecretStr("c" * 32),
        allowed_origin=AnyHttpUrl("https://schemasprint.test"),
        google_client_id=SecretStr("client"),
        google_client_secret=SecretStr("secret"),
        google_redirect_uri=AnyHttpUrl("https://schemasprint.test/api/v1/auth/google/callback"),
    )


def test_oauth_url_uses_pkce_and_exact_configured_redirect() -> None:
    configured = settings()
    state, verifier, ciphertext, _ = new_attempt(configured, "google")
    assert decrypt_verifier(configured, ciphertext) == verifier
    url = authorization_url(
        configured, "google", configured.oauth_provider("google"), state, verifier
    )
    query = parse_qs(urlparse(url).query)
    assert query["state"] == [state]
    assert query["redirect_uri"] == [str(configured.google_redirect_uri)]
    assert query["code_challenge_method"] == ["S256"]


@pytest.mark.asyncio
async def test_provider_response_is_reduced_to_verified_identity() -> None:
    configured = settings()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=(
                {"access_token": "opaque"}
                if request.url.path.endswith("/token")
                else {
                    "sub": "provider-sub",
                    "email": "user@example.test",
                    "email_verified": True,
                }
            ),
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        identity = await exchange_and_fetch(
            client,
            configured.oauth_provider("google"),
            "authorization-code",
            "v" * 43,
        )
    assert identity == OAuthIdentity(
        subject="provider-sub", email="user@example.test", email_verified=True
    )


@pytest.mark.asyncio
async def test_malformed_provider_response_is_rejected() -> None:
    configured = settings()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"access_token": "opaque"}
            if request.url.path.endswith("/token")
            else {"email": "missing-subject"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="subject"):
            await exchange_and_fetch(
                client,
                configured.oauth_provider("google"),
                "authorization-code",
                "v" * 43,
            )
