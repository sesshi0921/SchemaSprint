"""FastAPI wiring for learner-facing resources."""

# FastAPI dependency/query declarations intentionally call factory functions in
# defaults; this is how the framework builds the route contract.
# ruff: noqa: B008

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .config import Settings
from .database import Database
from .learner import (
    DashboardModel,
    Difficulty,
    DraftModel,
    DraftWriteModel,
    InputFormat,
    LearnerRepository,
    NoticePageModel,
    PolicyModel,
    ProblemPageModel,
    ProblemStatus,
    ProfileModel,
    ProfilePatchModel,
    SubmissionCreateModel,
    SubmissionModel,
)
from .problems import Locale, ProblemDetail
from .security import Principal, require_csrf

_ETAG_PATTERN = re.compile(r'^"([1-9][0-9]*)"$')
_ULID_PATTERN = r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$"
UlidPath = Annotated[str, Path(pattern=_ULID_PATTERN)]


async def _idempotent(
    database: Database,
    principal: Principal,
    operation: str,
    key: UUID,
    payload: object,
    action: Callable[[], Awaitable[tuple[int, object]]],
) -> Response:
    """Replay exact requests and reject key reuse with a different payload."""
    encoded = json.dumps(
        jsonable_encoder(payload), sort_keys=True, separators=(",", ":")
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    async with database.privileged() as connection:
        existing = await (
            await connection.execute(
                """
                SELECT request_digest, response_status, response_body
                FROM private.idempotency_records
                WHERE user_id=%s AND operation=%s AND key=%s
                FOR UPDATE
                """,
                (principal.user_id, operation, key),
            )
        ).fetchone()
        if existing is not None:
            if existing["request_digest"] != digest:
                raise HTTPException(status.HTTP_409_CONFLICT, "IDEMPOTENCY_KEY_REUSED")
            if existing["response_status"] is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "IDEMPOTENCY_IN_PROGRESS")
            response_body = existing["response_body"]
            if existing["response_status"] == status.HTTP_204_NO_CONTENT:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            replay_status = (
                status.HTTP_200_OK
                if operation == "create-submission"
                and int(existing["response_status"]) == status.HTTP_202_ACCEPTED
                else int(existing["response_status"])
            )
            return JSONResponse(content=response_body, status_code=replay_status)
        await connection.execute(
            """
            INSERT INTO private.idempotency_records
              (user_id, operation, key, request_digest)
            VALUES (%s,%s,%s,%s)
            """,
            (principal.user_id, operation, key, digest),
        )
    try:
        response_status, body = await action()
    except Exception:
        # A failed request must not poison a retry with an unbounded stale row.
        async with database.privileged() as connection:
            await connection.execute(
                """
                DELETE FROM private.idempotency_records
                WHERE user_id=%s AND operation=%s AND key=%s
                """,
                (principal.user_id, operation, key),
            )
        raise
    encoded_body = (
        None
        if response_status == status.HTTP_204_NO_CONTENT
        else jsonable_encoder(body)
    )
    async with database.privileged() as connection:
        await connection.execute(
            """
            UPDATE private.idempotency_records
            SET response_status=%s, response_body=%s::jsonb
            WHERE user_id=%s AND operation=%s AND key=%s
            """,
            (
                response_status,
                json.dumps(encoded_body),
                principal.user_id,
                operation,
                key,
            ),
        )
    if response_status == status.HTTP_204_NO_CONTENT:
        return Response(status_code=response_status)
    return JSONResponse(content=encoded_body, status_code=response_status)


def register_learner_routes(
    app: Any,
    database: Database,
    settings: Settings,
    required_principal: Callable[..., Awaitable[Principal]],
    learning_principal: Callable[..., Awaitable[Principal]],
) -> None:
    """Register routes against the app's existing authentication dependencies."""
    repository = LearnerRepository(database, settings)
    router = APIRouter(prefix="/api/v1")

    @router.get("/problems", response_model=ProblemPageModel)
    async def list_problems(
        principal: Principal = Depends(learning_principal),
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=30, ge=1, le=100),
        q: str | None = Query(default=None, max_length=200),
        difficulty: Difficulty | None = None,
        genre: str | None = Query(default=None, max_length=64),
        input_format: InputFormat | None = Query(default=None, alias="inputFormat"),
        problem_status: ProblemStatus | None = Query(default=None, alias="status"),
        published_from: date | None = Query(default=None, alias="publishedFrom"),
        published_to: date | None = Query(default=None, alias="publishedTo"),
        locale: Locale = Locale.EN,
    ) -> ProblemPageModel:
        return await repository.list_problems(
            principal,
            cursor=cursor,
            limit=limit,
            q=q,
            difficulty=difficulty,
            genre=genre,
            input_format=input_format,
            problem_status=problem_status,
            published_from=published_from,
            published_to=published_to,
            locale=locale,
        )

    @router.get("/problems/{problemId}", response_model=ProblemDetail)
    async def get_problem(
        problemId: UlidPath,
        principal: Principal = Depends(learning_principal),
        locale: Locale = Locale.EN,
        version: int | None = Query(default=None, ge=1),
    ) -> ProblemDetail:
        detail = await repository.detail(principal, problemId, locale, version)
        if detail is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROBLEM_NOT_FOUND")
        return detail

    @router.get("/problems/{problemId}/draft", response_model=DraftModel)
    async def get_draft(
        problemId: UlidPath,
        principal: Principal = Depends(learning_principal),
    ) -> DraftModel:
        draft = await repository.get_draft(principal, problemId)
        if draft is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "DRAFT_NOT_FOUND")
        return draft

    @router.put("/problems/{problemId}/draft", response_model=DraftModel)
    async def put_draft(
        request: Request,
        problemId: UlidPath,
        draft: DraftWriteModel,
        principal: Principal = Depends(learning_principal),
        if_match: str = Header(alias="If-Match"),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
    ) -> Response:
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        matched = _ETAG_PATTERN.fullmatch(if_match)
        if matched is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_IF_MATCH")
        expected = int(matched.group(1))

        async def action() -> tuple[int, object]:
            saved = await repository.put_draft(principal, problemId, expected, draft)
            return status.HTTP_200_OK, saved

        return await _idempotent(
            database,
            principal,
            f"put-draft:{problemId}",
            idempotency_key,
            {"draft": draft, "ifMatch": if_match},
            action,
        )

    @router.delete(
        "/problems/{problemId}/draft", status_code=status.HTTP_204_NO_CONTENT
    )
    async def delete_draft(
        request: Request,
        problemId: UlidPath,
        principal: Principal = Depends(learning_principal),
        if_match: str = Header(alias="If-Match"),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
    ) -> Response:
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        matched = _ETAG_PATTERN.fullmatch(if_match)
        if matched is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_IF_MATCH")
        expected = int(matched.group(1))

        async def action() -> tuple[int, object]:
            await repository.delete_draft(principal, problemId, expected)
            return status.HTTP_204_NO_CONTENT, None

        return await _idempotent(
            database,
            principal,
            f"delete-draft:{problemId}",
            idempotency_key,
            {"ifMatch": if_match},
            action,
        )

    @router.post(
        "/submissions",
        response_model=SubmissionModel,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_submission(
        request: Request,
        payload: SubmissionCreateModel,
        principal: Principal = Depends(learning_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
    ) -> Response:
        require_csrf(request, principal, settings.csrf_key.get_secret_value())

        async def action() -> tuple[int, object]:
            submission = await repository.create_submission(
                principal, payload, settings.jev_mode, idempotency_key
            )
            return status.HTTP_202_ACCEPTED, submission

        return await _idempotent(
            database,
            principal,
            "create-submission",
            idempotency_key,
            payload,
            action,
        )

    @router.get("/submissions/{submissionId}", response_model=SubmissionModel)
    async def get_submission(
        submissionId: UlidPath,
        principal: Principal = Depends(learning_principal),
    ) -> SubmissionModel:
        submission = await repository.get_submission(principal, submissionId)
        if submission is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SUBMISSION_NOT_FOUND")
        return submission

    @router.get("/dashboard", response_model=DashboardModel)
    async def get_dashboard(
        principal: Principal = Depends(learning_principal),
        from_date: date | None = Query(default=None, alias="from"),
        to_date: date | None = Query(default=None, alias="to"),
    ) -> DashboardModel:
        return await repository.dashboard(principal, from_date, to_date)

    @router.get("/notices", response_model=NoticePageModel)
    async def list_notices(
        principal: Principal = Depends(learning_principal),
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=30, ge=1, le=100),
        locale: Locale = Locale.EN,
    ) -> NoticePageModel:
        return await repository.list_notices(
            principal, cursor=cursor, limit=limit, locale=locale
        )

    @router.put(
        "/notices/{noticeVersionId}/read", status_code=status.HTTP_204_NO_CONTENT
    )
    async def mark_notice_read(
        request: Request,
        noticeVersionId: UlidPath,
        principal: Principal = Depends(learning_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
    ) -> Response:
        require_csrf(request, principal, settings.csrf_key.get_secret_value())

        async def action() -> tuple[int, object]:
            await repository.mark_notice_read(principal, noticeVersionId)
            return status.HTTP_204_NO_CONTENT, None

        return await _idempotent(
            database,
            principal,
            f"read-notice:{noticeVersionId}",
            idempotency_key,
            {},
            action,
        )

    @router.get("/policies", response_model=list[PolicyModel])
    async def list_policies(
        principal: Principal = Depends(required_principal),
    ) -> list[PolicyModel]:
        return await repository.policies(principal)

    @router.get("/profile", response_model=ProfileModel)
    async def get_profile(
        principal: Principal = Depends(required_principal),
    ) -> ProfileModel:
        profile = await repository.profile(principal)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROFILE_NOT_FOUND")
        return profile

    @router.patch("/profile", response_model=ProfileModel)
    async def update_profile(
        request: Request,
        patch: ProfilePatchModel,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
    ) -> Response:
        require_csrf(request, principal, settings.csrf_key.get_secret_value())

        async def action() -> tuple[int, object]:
            profile = await repository.update_profile(
                principal,
                display_name=patch.displayName,
                locale=patch.locale,
                theme=patch.theme,
            )
            return status.HTTP_200_OK, profile

        return await _idempotent(
            database,
            principal,
            "update-profile",
            idempotency_key,
            patch,
            action,
        )

    app.include_router(router)


__all__ = ["register_learner_routes"]
