from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from .config import OAuthProviderSettings, Settings


@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    subject: str
    email: str | None
    email_verified: bool


def _fernet(settings: Settings) -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.csrf_key.get_secret_value().encode()).digest()
    )
    return Fernet(key)


def new_attempt(settings: Settings, provider: str) -> tuple[str, str, bytes, datetime]:
    """Return public state, verifier, encrypted verifier and expiry."""
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(48)
    expires = datetime.now(UTC) + timedelta(minutes=10)
    encrypted = _fernet(settings).encrypt(verifier.encode())
    return state, verifier, encrypted, expires


def decrypt_verifier(settings: Settings, ciphertext: bytes) -> str:
    try:
        verifier = _fernet(settings).decrypt(ciphertext, ttl=600).decode()
    except (InvalidToken, UnicodeDecodeError) as error:
        raise ValueError("invalid OAuth verifier") from error
    if not 43 <= len(verifier) <= 128:
        raise ValueError("invalid OAuth verifier")
    return verifier


def state_hash(state: str, pepper: str) -> str:
    return hashlib.sha256((pepper + state).encode()).hexdigest()


def authorization_url(
    settings: Settings,
    provider: str,
    config: OAuthProviderSettings,
    state: str,
    verifier: str,
) -> str:
    if not config.configured or config.redirect_uri is None or config.client_id is None:
        raise ValueError("OAuth provider is not configured")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    params = {
        "client_id": config.client_id.get_secret_value(),
        "redirect_uri": str(config.redirect_uri),
        "response_type": "code",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if provider == "google":
        params["scope"] = "openid email profile"
        params["access_type"] = "online"
    else:
        params["scope"] = "read:user user:email"
    return f"{str(config.authorize_url)}?{urlencode(params)}"


async def exchange_and_fetch(
    client: httpx.AsyncClient,
    config: OAuthProviderSettings,
    code: str,
    verifier: str,
) -> OAuthIdentity:
    if (
        not config.configured
        or config.client_id is None
        or config.client_secret is None
    ):
        raise ValueError("OAuth provider is not configured")
    token_response = await client.post(
        str(config.token_url),
        data={
            "client_id": config.client_id.get_secret_value(),
            "client_secret": config.client_secret.get_secret_value(),
            "code": code,
            "redirect_uri": str(config.redirect_uri),
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        headers={"Accept": "application/json"},
    )
    if token_response.status_code != 200:
        raise ValueError("OAuth token exchange failed")
    token_payload = token_response.json()
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not 1 <= len(access_token) <= 4096:
        raise ValueError("OAuth token response invalid")
    user_response = await client.get(
        str(config.userinfo_url),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    if user_response.status_code != 200:
        raise ValueError("OAuth userinfo request failed")
    payload = user_response.json()
    subject = payload.get("sub")
    if not isinstance(subject, str):
        subject = payload.get("id")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
        raise ValueError("OAuth identity subject invalid")
    email = payload.get("email")
    if email is not None and (not isinstance(email, str) or len(email) > 320):
        email = None
    verified = payload.get("email_verified", False)
    return OAuthIdentity(subject=subject, email=email, email_verified=verified is True)
