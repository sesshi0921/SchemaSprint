from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict

from .config import Settings, get_settings
from .database import Database
from .errors import (
    http_exception_handler,
    problem_response,
    request_validation_handler,
)
from .http_security import (
    UNSAFE_METHODS,
    InProcessRateLimiter,
    InvalidContentLength,
    RequestBodyTooLarge,
    client_address,
    parse_content_length,
    request_source_key,
    same_origin,
    security_headers,
)
from .problems import Locale, ProblemDetail, ProblemRepository
from .security import SESSION_COOKIE, Principal, csrf_token


class SessionGates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowlisted: bool
    identityVerified: bool
    ageDeclared: bool
    policiesCurrent: bool
    mfaCurrent: bool


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authenticated: bool
    csrfToken: str | None
    gates: SessionGates | None = None


def create_app(
    settings: Settings | None = None, database: Database | None = None
) -> FastAPI:
    resolved = settings or get_settings()
    database = database or Database(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await database.open()
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(title="SchemaSprint BFF", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.database = database
    ip_rate_limiter = InProcessRateLimiter(
        resolved.rate_limit_capacity,
        resolved.rate_limit_window_seconds,
        resolved.rate_limit_max_keys,
    )
    user_rate_limiter = InProcessRateLimiter(
        resolved.rate_limit_capacity,
        resolved.rate_limit_window_seconds,
        resolved.rate_limit_max_keys,
    )
    # Keep the IP-wide limiter as the public state handle for observability;
    # separate caches prevent the action-key cache from evicting IP buckets
    # when the configured bound is intentionally small.
    app.state.rate_limiter = ip_rate_limiter
    app.state.user_rate_limiter = user_rate_limiter
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Never reflect a client-controlled value into a response header.
        request.state.request_id = str(uuid4())
        try:
            advertised_length = parse_content_length(
                request.headers.get("Content-Length")
            )
        except InvalidContentLength:
            response = problem_response(
                request,
                status.HTTP_400_BAD_REQUEST,
                "INVALID_CONTENT_LENGTH",
                "Request rejected",
            )
            return _secure_response(request, response, resolved)
        if (
            advertised_length is not None
            and advertised_length > resolved.request_body_limit_bytes
        ):
            response = problem_response(
                request,
                status.HTTP_413_CONTENT_TOO_LARGE,
                "REQUEST_BODY_TOO_LARGE",
                "Request rejected",
                retryable=False,
            )
            return _secure_response(request, response, resolved)

        if request.method.upper() in UNSAFE_METHODS and not same_origin(
            request, str(resolved.allowed_origin)
        ):
            response = problem_response(
                request,
                status.HTTP_403_FORBIDDEN,
                "ORIGIN_CHECK_FAILED",
                "Request rejected",
            )
            return _secure_response(request, response, resolved)

        if resolved.rate_limit_enabled and request.method.upper() != "OPTIONS":
            source = request_source_key(
                request,
                resolved.trusted_proxy_cidrs,
                resolved.session_pepper.get_secret_value(),
            )
            address = client_address(request, resolved.trusted_proxy_cidrs)
            path_digest = sha256(request.url.path.encode("utf-8")).hexdigest()[:24]
            decisions = (
                # Keep an address-wide bucket even when an attacker rotates
                # session cookies; the second bucket gives authenticated
                # users/action paths their own tighter accounting.
                await ip_rate_limiter.check(f"ip:{address}"),
                await user_rate_limiter.check(f"user:{source}:path:{path_digest}"),
            )
            rejected = next((item for item in decisions if not item.allowed), None)
            if rejected is not None:
                response = problem_response(
                    request,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "RATE_LIMITED",
                    "Request rejected",
                    retryable=True,
                )
                response.headers["Retry-After"] = str(rejected.retry_after_seconds)
                response.headers["RateLimit-Limit"] = str(resolved.rate_limit_capacity)
                response.headers["RateLimit-Remaining"] = "0"
                return _secure_response(request, response, resolved)

        original_receive = request._receive
        received_bytes = 0

        async def limited_receive():  # type: ignore[no-untyped-def]
            nonlocal received_bytes
            message = await original_receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > resolved.request_body_limit_bytes:
                    raise RequestBodyTooLarge
            return message

        request._receive = limited_receive
        try:
            # Drain through the bounded receive wrapper even when a route does
            # not inspect its body (for example, a GET with an unexpected body).
            # Starlette caches this bounded body for downstream JSON parsing.
            await request.body()
            response = await call_next(request)
        except RequestBodyTooLarge:
            response = problem_response(
                request,
                status.HTTP_413_CONTENT_TOO_LARGE,
                "REQUEST_BODY_TOO_LARGE",
                "Request rejected",
                retryable=False,
            )
        response = _secure_response(request, response, resolved)
        return response

    def _secure_response(  # type: ignore[no-untyped-def]
        request: Request, response, settings: Settings
    ):
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers.update(
            security_headers(production=settings.environment.value == "production")
        )
        return response

    async def optional_principal(request: Request) -> Principal | None:
        token = request.cookies.get(SESSION_COOKIE)
        if token is None or not 32 <= len(token) <= 512:
            return None
        return await database.principal_for_token(token)

    async def required_principal(
        principal: Annotated[Principal | None, Depends(optional_principal)],
    ) -> Principal:
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_REQUIRED")
        return principal

    async def learning_principal(
        principal: Annotated[Principal, Depends(required_principal)],
    ) -> Principal:
        if not await database.can_learn(principal):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "LEARNING_ACCESS_REQUIRED")
        return principal

    @app.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/api/v1/session", response_model=SessionResponse)
    async def session(
        principal: Annotated[Principal | None, Depends(optional_principal)],
    ) -> SessionResponse:
        if principal is None:
            return SessionResponse(authenticated=False, csrfToken=None)
        return SessionResponse(
            authenticated=True,
            csrfToken=csrf_token(
                principal.session_id, resolved.csrf_key.get_secret_value()
            ),
            gates=SessionGates(
                allowlisted=principal.allowlisted,
                identityVerified=principal.identity_verified,
                ageDeclared=principal.age_declared,
                policiesCurrent=principal.policies_current,
                mfaCurrent=principal.mfa_current,
            ),
        )

    @app.get("/api/v1/problems/today", response_model=ProblemDetail)
    async def today(
        principal: Annotated[Principal, Depends(learning_principal)],
        locale: Locale = Locale.EN,
    ) -> ProblemDetail:
        row = await ProblemRepository(database).today(principal, locale)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "TODAY_PROBLEM_NOT_FOUND")
        return row

    @app.exception_handler(Exception)
    async def unhandled(request: Request, _: Exception):  # type: ignore[no-untyped-def]
        return problem_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Internal error",
            retryable=True,
        )

    return app
