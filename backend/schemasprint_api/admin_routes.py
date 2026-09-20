# ruff: noqa: E501, B008, E702, I001

"""HTTP routes for owner/admin workflows."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Path,
    Request,
    Response,
    status,
)


from .admin import (
    AdminNotice,
    AdminProblemVersion,
    AdminRepository,
    Approval,
    ApprovalCreate,
    BatchCreate,
    Decision,
    Entitlement,
    EntitlementChange,
    NoticeWrite,
    ProblemVersionWrite,
    PublishProblem,
    require_admin_role,
)
from .config import Settings
from .database import Database
from .learner import CommunityPostModel, JobModel, ReportModel
from .security import Principal, require_csrf
from .learner_routes import _idempotent

AdminUlid = Annotated[str, Path(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")]


async def _admin_principal(principal: Principal = Depends()) -> Principal:
    # Replaced by the dependency supplied to register_admin_routes.
    return principal


def register_admin_routes(
    app: Any,
    database: Database,
    settings: Settings,
    required_principal: Callable[..., Awaitable[Principal]],
) -> None:
    repository = AdminRepository(database)
    router = APIRouter(prefix="/api/v1/admin")

    def check(principal: Principal, proof: str, *, owner: bool = False) -> None:
        require_admin_role(principal, owner=owner)
        if len(proof) < 32 or not principal.mfa_current:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "RECENT_MFA_REQUIRED")

    @router.post(
        "/problems/{problemId}/versions",
        response_model=AdminProblemVersion,
        status_code=201,
    )
    async def create_problem_version(
        request: Request,
        problemId: AdminUlid,
        payload: ProblemVersionWrite,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-create-problem-version",
            idempotency_key,
            {"problemId": problemId, **payload.model_dump(mode="json")},
            lambda: _created(repository.create_version(principal, problemId, payload)),
        )

    @router.get(
        "/problem-versions/{problemVersionId}", response_model=AdminProblemVersion
    )
    async def get_problem_version(
        problemVersionId: AdminUlid, principal: Principal = Depends(required_principal)
    ) -> AdminProblemVersion:
        require_admin_role(principal)
        result = await repository.get_version(problemVersionId)
        if result is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROBLEM_VERSION_NOT_FOUND")
        return result

    @router.put(
        "/problem-versions/{problemVersionId}", response_model=AdminProblemVersion
    )
    async def replace_problem_version(
        request: Request,
        problemVersionId: AdminUlid,
        payload: ProblemVersionWrite,
        if_match: str = Header(alias="If-Match"),
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        if (
            len(if_match) != 66
            or not if_match.startswith('"')
            or not if_match.endswith('"')
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_ETAG")
        expected = if_match[1:-1]
        return await _idempotent(
            database,
            principal,
            "admin-replace-problem-version",
            idempotency_key,
            {
                "id": problemVersionId,
                "payload": payload.model_dump(mode="json"),
                "etag": expected,
            },
            lambda: _ok(
                repository.replace_version(
                    principal, problemVersionId, payload, expected
                )
            ),
        )

    @router.post(
        "/problem-versions/{problemVersionId}/validate",
        response_model=JobModel,
        status_code=202,
    )
    async def validate_problem_version(
        request: Request,
        problemVersionId: AdminUlid,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-validate-problem-version",
            idempotency_key,
            {"id": problemVersionId},
            lambda: _accepted(repository.validate_version(principal, problemVersionId)),
        )

    @router.post(
        "/problem-versions/{problemVersionId}/publish",
        response_model=AdminProblemVersion,
    )
    async def publish_problem_version(
        request: Request,
        problemVersionId: AdminUlid,
        payload: PublishProblem,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-publish-problem-version",
            idempotency_key,
            {"id": problemVersionId, **payload.model_dump(mode="json")},
            lambda: _ok(
                repository.publish_version(principal, problemVersionId, payload)
            ),
        )

    @router.get("/posts", response_model=dict)
    async def list_held_posts(
        state: str = Query("held", pattern="^(held|approved|rejected)$"),
        limit: int = Query(30, ge=1, le=100),
        principal: Principal = Depends(required_principal),
    ) -> dict[str, Any]:
        require_admin_role(principal)
        return {
            "items": [
                p.model_dump(mode="json", by_alias=True)
                for p in await repository.posts(state, limit)
            ]
        }

    @router.post("/posts/{postId}/decision", response_model=CommunityPostModel)
    async def decide_post(
        request: Request,
        postId: AdminUlid,
        payload: Decision,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-decide-post",
            idempotency_key,
            {"id": postId, **payload.model_dump()},
            lambda: _ok(
                repository.decide_post(
                    principal, postId, payload.decision, payload.reason
                )
            ),
        )

    @router.post("/notices", response_model=AdminNotice, status_code=201)
    async def create_notice(
        request: Request,
        payload: NoticeWrite,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-create-notice",
            idempotency_key,
            payload,
            lambda: _created(repository.create_notice(principal, payload)),
        )

    @router.post(
        "/notices/{noticeId}/versions", response_model=AdminNotice, status_code=201
    )
    async def create_notice_version(
        request: Request,
        noticeId: AdminUlid,
        payload: NoticeWrite,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-create-notice-version",
            idempotency_key,
            {"id": noticeId, **payload.model_dump()},
            lambda: _created(repository.create_notice(principal, payload, noticeId)),
        )

    @router.post(
        "/notice-versions/{noticeVersionId}/publish", response_model=AdminNotice
    )
    async def publish_notice(
        request: Request,
        noticeVersionId: AdminUlid,
        payload: dict[str, str],
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        digest = payload.get("approvedTargetDigest", "")
        return await _idempotent(
            database,
            principal,
            "admin-publish-notice",
            idempotency_key,
            {"id": noticeVersionId, "digest": digest},
            lambda: _ok(repository.publish_notice(principal, noticeVersionId, digest)),
        )

    @router.post("/problem-batches", response_model=JobModel, status_code=202)
    async def generate_batch(
        request: Request,
        payload: BatchCreate,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof, owner=True)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-generate-problem-batch",
            idempotency_key,
            payload,
            lambda: _accepted(repository.batch(principal, payload.calendarMonth)),
        )

    @router.post("/reports/{reportId}/decision", response_model=ReportModel)
    async def decide_report(
        request: Request,
        reportId: AdminUlid,
        payload: Decision,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-decide-report",
            idempotency_key,
            {"id": reportId, **payload.model_dump()},
            lambda: _ok(
                repository.decide_report(
                    principal, reportId, payload.decision, payload.reason
                )
            ),
        )

    @router.post("/approvals", response_model=Approval, status_code=201)
    async def create_approval(
        request: Request,
        payload: ApprovalCreate,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-create-approval",
            idempotency_key,
            payload,
            lambda: _created(repository.approval(principal, payload)),
        )

    @router.post("/entitlements", response_model=Entitlement)
    async def change_entitlement(
        request: Request,
        payload: EntitlementChange,
        principal: Principal = Depends(required_principal),
        csrf: str = Header(alias="X-CSRF-Token"),
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        proof: str = Header(alias="X-Reauthentication-Proof"),
    ) -> Response:
        check(principal, proof, owner=True)
        require_csrf(request, principal, settings.csrf_key.get_secret_value())
        return await _idempotent(
            database,
            principal,
            "admin-change-entitlement",
            idempotency_key,
            payload,
            lambda: _ok(repository.entitlement(principal, payload)),
        )

    app.include_router(router)


async def _created(operation: Awaitable[Any]) -> tuple[int, Any]:
    return status.HTTP_201_CREATED, await operation


async def _ok(operation: Awaitable[Any]) -> tuple[int, Any]:
    return status.HTTP_200_OK, await operation


async def _accepted(operation: Awaitable[Any]) -> tuple[int, Any]:
    return status.HTTP_202_ACCEPTED, await operation
