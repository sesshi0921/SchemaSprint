from typing import Any

import psycopg
import pytest
from pydantic import SecretStr, ValidationError
from schemasprint_api.config import Environment, JevMode, Settings
from schemasprint_api.database import Database
from schemasprint_api.security import csrf_token, token_digest


def settings(database_uri: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": Environment.TEST,
        "database_dsn": SecretStr(database_uri),
        "session_pepper": SecretStr("p" * 32),
        "csrf_key": SecretStr("c" * 32),
        "allowed_origin": "https://schemasprint.test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_secret_derived_tokens_are_deterministic_and_separated() -> None:
    assert token_digest("token", "p" * 32) == token_digest("token", "p" * 32)
    assert token_digest("token", "p" * 32) != csrf_token("token", "c" * 32)


def test_short_security_keys_are_rejected(database_uri: str) -> None:
    with pytest.raises(ValidationError):
        settings(database_uri, csrf_key=SecretStr("short"))
    with pytest.raises(ValidationError):
        settings(database_uri, session_pepper=SecretStr("short"))


def test_request_body_limit_defaults_to_one_mib_and_cannot_exceed_it(
    database_uri: str,
) -> None:
    configured = settings(database_uri)
    assert configured.request_body_limit_bytes == 1024 * 1024
    with pytest.raises(ValidationError):
        settings(database_uri, request_body_limit_bytes=1024 * 1024 + 1)


def test_stub_cannot_start_outside_development_or_test(database_uri: str) -> None:
    with pytest.raises(ValidationError):
        settings(
            database_uri,
            environment=Environment.PRODUCTION,
            jev_mode=JevMode.STUB,
        )


def test_external_jev_requires_explicit_credentials(database_uri: str) -> None:
    with pytest.raises(ValidationError):
        settings(database_uri, jev_mode=JevMode.EXTERNAL)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_external_jev_requires_https_outside_development(
    database_uri: str, environment: str
) -> None:
    with pytest.raises(ValidationError):
        settings(
            database_uri,
            environment=environment,
            jev_mode=JevMode.EXTERNAL,
            jev_base_url="http://jev.internal",
            jev_api_key=SecretStr("jev-secret"),
        )


def test_external_jev_https_is_accepted_in_staging(database_uri: str) -> None:
    configured = settings(
        database_uri,
        environment="staging",
        jev_mode=JevMode.EXTERNAL,
        jev_base_url="https://jev.internal",
        jev_api_key=SecretStr("jev-secret"),
    )
    assert configured.jev_base_url is not None


@pytest.mark.asyncio
async def test_session_principal_uses_real_gates_and_roles(
    db: psycopg.Connection[Any], database_uri: str
) -> None:
    auth_id = "77777777-7777-7777-7777-777777777777"
    user_id = "01ARZ3NDEKTSV4RRFFQ69G5FBS"
    session_id = "01ARZ3NDEKTSV4RRFFQ69G5FBT"
    allowlist_id = "01ARZ3NDEKTSV4RRFFQ69G5FBV"
    raw_token = "session-token-with-at-least-32-bytes"
    configured = settings(database_uri)
    digest = token_digest(raw_token, configured.session_pepper.get_secret_value())
    db.execute("INSERT INTO auth.users(id) VALUES (%s)", (auth_id,))
    db.execute(
        "INSERT INTO public.users(id, auth_user_id, display_name) VALUES (%s, %s, 'Learner')",  # noqa: E501
        (user_id, auth_id),
    )
    db.execute(
        "INSERT INTO public.age_declarations(user_id, is_at_least_16) VALUES (%s, true)",  # noqa: E501
        (user_id,),
    )
    db.execute(
        "INSERT INTO public.provider_identities(user_id, issuer, subject, verified_at) VALUES (%s, 'google', 'subject-session', now())",  # noqa: E501
        (user_id,),
    )
    db.execute(
        "INSERT INTO private.identity_allowlist(id, issuer, subject, bound_at) VALUES (%s, 'google', 'subject-session', now())",  # noqa: E501
        (allowlist_id,),
    )
    db.execute(
        "INSERT INTO public.role_grants(user_id, role, reason) VALUES (%s, 'owner', 'bootstrap')",  # noqa: E501
        (user_id,),
    )
    db.execute(
        "INSERT INTO private.sessions(id, user_id, token_hash, expires_at, mfa_authenticated_at) VALUES (%s, %s, %s, now() + interval '1 hour', now())",  # noqa: E501
        (session_id, user_id, digest),
    )
    db.commit()
    database = Database(configured)
    await database.open()
    try:
        principal = await database.principal_for_token(raw_token)
    finally:
        await database.close()
    assert principal is not None
    assert principal.user_id == user_id
    assert principal.roles == frozenset({"owner"})
    assert principal.allowlisted
    assert principal.identity_verified
    assert principal.age_declared
    assert principal.policies_current
    assert principal.mfa_current
