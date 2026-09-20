from datetime import date
from typing import Any

import httpx
import pytest
from pydantic import AnyHttpUrl, SecretStr
from schemasprint_api.app import create_app
from schemasprint_api.config import Environment, Settings
from schemasprint_api.database import Database
from schemasprint_api.problems import Locale, ProblemDetail, RubricSummary
from schemasprint_api.security import SESSION_COOKIE, Principal, csrf_token


class FakeDatabase(Database):
    def __init__(self, principal: Principal | None, can_learn: bool = True) -> None:
        self.principal = principal
        self.learning_allowed = can_learn
        self.can_learn_calls = 0
        self.opened = False

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.opened = False

    async def principal_for_token(self, raw_token: str) -> Principal | None:
        return self.principal if raw_token == "t" * 32 else None

    async def can_learn(self, principal: Principal) -> bool:
        self.can_learn_calls += 1
        return self.learning_allowed


def make_settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_dsn=SecretStr("postgresql://unused"),
        session_pepper=SecretStr("p" * 32),
        csrf_key=SecretStr("c" * 32),
        allowed_origin=AnyHttpUrl("https://schemasprint.test"),
    )


@pytest.mark.asyncio
async def test_anonymous_session_is_explicit_and_security_headers_are_set() -> None:
    fake = FakeDatabase(None)
    app = create_app(make_settings(), fake)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
        ) as client,
    ):
        response = await client.get("/api/v1/session")
    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "csrfToken": None,
        "gates": None,
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    assert not fake.opened


@pytest.mark.asyncio
async def test_authenticated_session_reports_actual_gate_state() -> None:
    principal = Principal(
        session_id="01ARZ3NDEKTSV4RRFFQ69G5FBW",
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FBX",
        auth_user_id="88888888-8888-8888-8888-888888888888",
        roles=frozenset({"learner"}),
        allowlisted=True,
        identity_verified=True,
        age_declared=True,
        policies_current=False,
        mfa_current=False,
    )
    configured = make_settings()
    app = create_app(configured, FakeDatabase(principal))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
            cookies={SESSION_COOKIE: "t" * 32},
        ) as client,
    ):
        response = await client.get("/api/v1/session")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["authenticated"] is True
    assert body["gates"]["policiesCurrent"] is False
    assert body["csrfToken"] == csrf_token(
        principal.session_id, configured.csrf_key.get_secret_value()
    )


@pytest.mark.asyncio
async def test_oversized_or_short_cookie_is_rejected_without_lookup() -> None:
    principal = Principal(
        session_id="01ARZ3NDEKTSV4RRFFQ69G5FBW",
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FBX",
        auth_user_id="88888888-8888-8888-8888-888888888888",
        roles=frozenset(),
        allowlisted=True,
        identity_verified=True,
        age_declared=True,
        policies_current=True,
        mfa_current=False,
    )
    app = create_app(make_settings(), FakeDatabase(principal))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
            cookies={SESSION_COOKIE: "short"},
        ) as client,
    ):
        response = await client.get("/api/v1/session")
    assert response.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_request_validation_errors_are_safe_problem_details() -> None:
    principal = Principal(
        session_id="01ARZ3NDEKTSV4RRFFQ69G5FBW",
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FBX",
        auth_user_id="88888888-8888-8888-8888-888888888888",
        roles=frozenset({"learner"}),
        allowlisted=True,
        identity_verified=True,
        age_declared=True,
        policies_current=True,
        mfa_current=False,
    )
    app = create_app(make_settings(), FakeDatabase(principal))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
            cookies={SESSION_COOKIE: "t" * 32},
        ) as client,
    ):
        response = await client.get(
            "/api/v1/problems/today?locale=not-a-locale&secret=do-not-echo"
        )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "REQUEST_VALIDATION_FAILED"
    assert "not-a-locale" not in response.text
    assert "do-not-echo" not in response.text


@pytest.mark.asyncio
async def test_learning_gate_returns_403_before_learning_repository_access() -> None:
    principal = Principal(
        session_id="01ARZ3NDEKTSV4RRFFQ69G5FBW",
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FBX",
        auth_user_id="88888888-8888-8888-8888-888888888888",
        roles=frozenset({"learner"}),
        allowlisted=False,
        identity_verified=True,
        age_declared=True,
        policies_current=True,
        mfa_current=False,
    )
    fake = FakeDatabase(principal, can_learn=False)
    app = create_app(make_settings(), fake)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
            cookies={SESSION_COOKIE: "t" * 32},
        ) as client,
    ):
        response = await client.get("/api/v1/problems/today")
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "LEARNING_ACCESS_REQUIRED"
    assert fake.can_learn_calls == 1


@pytest.mark.asyncio
async def test_today_serializes_problem_detail_with_state_and_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = Principal(
        session_id="01ARZ3NDEKTSV4RRFFQ69G5FBW",
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FBX",
        auth_user_id="88888888-8888-8888-8888-888888888888",
        roles=frozenset({"learner"}),
        allowlisted=True,
        identity_verified=True,
        age_declared=True,
        policies_current=True,
        mfa_current=False,
    )
    expected = ProblemDetail(
        id="01ARZ3NDEKTSV4RRFFQ69G5FBY",
        version=1,
        title="Design",
        difficulty="easy",
        genre="oltp",
        inputFormat="mixed",
        tags=["joins"],
        publicationDate=date(2026, 9, 20),
        passed=False,
        submitted=True,
        translationStatus="unavailable",
        problemVersionId="01ARZ3NDEKTSV4RRFFQ69G5FBZ",
        statement="English fallback",
        officialAnswer={"schemaVersion": 1, "tables": [], "relationships": []},
        explanation="English explanation fallback",
        requestedLocale=Locale.JA,
        rubricSummary=[
            RubricSummary(
                id="01ARZ3NDEKTSV4RRFFQ69G5FC0",
                description="Entity",
                weight=1,
                critical=True,
                implicit=False,
            )
        ],
    )

    async def fake_today(
        _repository: object, current_principal: Principal, locale: Locale
    ) -> ProblemDetail:
        assert current_principal == principal
        assert locale is Locale.JA
        return expected

    monkeypatch.setattr("schemasprint_api.app.ProblemRepository.today", fake_today)
    app = create_app(make_settings(), FakeDatabase(principal))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://schemasprint.test",
            cookies={SESSION_COOKIE: "t" * 32},
        ) as client,
    ):
        response = await client.get("/api/v1/problems/today?locale=ja")
    assert response.status_code == 200
    body = response.json()
    assert body["requestedLocale"] == "ja"
    assert body["translationStatus"] == "unavailable"
    assert body["submitted"] is True
    assert body["passed"] is False
    assert len(body["rubricSummary"]) == 1
