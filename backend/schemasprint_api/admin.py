# ruff: noqa: E501, B008, E702, UP017, UP037, I001

"""Owner/admin content workflows.

All writes are service-role transactions with an explicit application role
check and an audit row.  The service role is used only because these records
are intentionally outside learner RLS; no caller-controlled SQL is accepted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo
from typing import Any, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb
from ulid import new as new_ulid

from .core import CoreValidationError, validate_canonical_schema
from .database import Database
from .learner import (
    CanonicalSchemaModel,
    CommunityPostModel,
    Difficulty,
    InputFormat,
    JobModel,
    ReportModel,
)
from .security import Principal


class RubricWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
    descriptionEn: str = Field(min_length=1, max_length=5000)
    weight: int = Field(ge=1, le=1_000_000)
    critical: bool
    implicit: bool
    textualDerivation: str | None = Field(default=None, max_length=5000)
    evaluatorSpec: dict[str, Any]

    @model_validator(mode="after")
    def valid_implicit(self) -> "RubricWrite":
        if self.critical and self.implicit:
            raise ValueError("critical and implicit cannot both be true")
        if self.implicit and not self.textualDerivation:
            raise ValueError("implicit rubric requires textual derivation")
        return self


class ProblemVersionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    statementEn: str = Field(min_length=1, max_length=100_000)
    officialSolution: CanonicalSchemaModel
    explanationEn: str = Field(min_length=1, max_length=100_000)
    difficulty: Difficulty
    genre: str = Field(min_length=1, max_length=64)
    inputFormat: InputFormat
    tags: list[str] = Field(max_length=50)
    rubric: list[RubricWrite] = Field(min_length=1, max_length=2000)


class AdminProblemVersion(ProblemVersionWrite):
    id: str
    problemId: str
    version: int
    state: str
    contentDigest: str
    validationJobId: str | None = None


class NoticeWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titleEn: str = Field(min_length=1, max_length=200)
    bodyEn: str = Field(min_length=1, max_length=100_000)
    targetDigest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdminNotice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titleEn: str
    bodyEn: str
    targetDigest: str
    id: str
    versionId: str
    version: int
    state: str
    publishedAt: datetime | None = None


class PublishProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publicationDate: date
    approvedTargetDigest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["correction", "notice"]
    targetId: str = Field(pattern=r"^[0-9A-HJKMNP-TV-Z]{26}$")
    targetDigest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=2000)


class Approval(BaseModel):
    id: str
    action: str
    targetId: str
    targetDigest: str
    approvedAt: datetime


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    reason: str = Field(min_length=1, max_length=2000)


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calendarMonth: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")


class EntitlementChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    userId: str = Field(pattern=r"^[0-9A-HJKMNP-TV-Z]{26}$")
    action: Literal["grant", "revoke"]
    validUntil: datetime | None = None
    reason: str = Field(min_length=1, max_length=500)


class Entitlement(BaseModel):
    premium: bool
    validUntil: datetime | None = None
    billingEnabled: Literal[False] = False
    adsEnabled: Literal[False] = False


def _require_admin(principal: Principal, proof: str, *, owner: bool = False) -> None:
    role = "owner" if owner else None
    if role is not None:
        allowed = role in principal.roles
    else:
        allowed = bool(principal.roles & {"admin", "owner"})
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ADMIN_ROLE_REQUIRED")
    if len(proof) < 32 or not principal.mfa_current:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "RECENT_MFA_REQUIRED")


def require_admin_role(principal: Principal, *, owner: bool = False) -> None:
    allowed = (
        ("owner" in principal.roles)
        if owner
        else bool(principal.roles & {"admin", "owner"})
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ADMIN_ROLE_REQUIRED")


def _digest(payload: ProblemVersionWrite) -> str:
    raw = json.dumps(
        payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _version(row: dict[str, Any], rubric: list[dict[str, Any]]) -> AdminProblemVersion:
    return AdminProblemVersion.model_validate(
        {
            "title": row["title"],
            "statementEn": row["statement_en"],
            "officialSolution": row["official_solution"],
            "explanationEn": row["explanation_en"],
            "difficulty": row["difficulty"],
            "genre": row["genre"],
            "inputFormat": row["input_format"],
            "tags": list(row["tags"] or []),
            "rubric": rubric,
            "id": str(row["id"]),
            "problemId": str(row["problem_id"]),
            "version": row["version"],
            "state": row["state"],
            "contentDigest": row["normalized_hash"],
            "validationJobId": row.get("validation_job_id"),
        }
    )


class AdminRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def _audit(
        self, c: Any, actor: str, action: str, kind: str, target: str, reason: str
    ) -> None:
        await c.execute(
            "INSERT INTO private.admin_audit(actor_user_id,action,target_kind,target_id,reason) VALUES (%s,%s,%s,%s,%s)",
            (actor, action, kind, target, reason),
        )

    async def get_version(self, version_id: str) -> AdminProblemVersion | None:
        async with self.database.privileged() as c:
            row = await (
                await c.execute(
                    "SELECT * FROM public.problem_versions WHERE id=%s", (version_id,)
                )
            ).fetchone()
            if row is None:
                return None
            rubrics = await (
                await c.execute(
                    "SELECT id::text,description_en,weight,is_critical,is_implicit,textual_derivation,evaluator_spec FROM public.rubric_items WHERE problem_version_id=%s ORDER BY ordinal",
                    (version_id,),
                )
            ).fetchall()
        return _version(
            row,
            [
                {
                    "id": r["id"],
                    "descriptionEn": r["description_en"],
                    "weight": r["weight"],
                    "critical": r["is_critical"],
                    "implicit": r["is_implicit"],
                    "textualDerivation": r["textual_derivation"],
                    "evaluatorSpec": r["evaluator_spec"],
                }
                for r in rubrics
            ],
        )

    async def create_version(
        self, principal: Principal, problem_id: str, payload: ProblemVersionWrite
    ) -> AdminProblemVersion:
        digest = _digest(payload)
        vid = str(new_ulid())
        async with self.database.privileged() as c:
            p = await (
                await c.execute(
                    "SELECT id FROM public.problems WHERE id=%s FOR UPDATE",
                    (problem_id,),
                )
            ).fetchone()
            if p is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "PROBLEM_NOT_FOUND")
            row = await (
                await c.execute(
                    "SELECT coalesce(max(version),0)+1 AS version FROM public.problem_versions WHERE problem_id=%s",
                    (problem_id,),
                )
            ).fetchone()
            assert row is not None
            version = int(row["version"])
            try:
                await c.execute(
                    "INSERT INTO public.problem_versions(id,problem_id,version,title,statement_en,official_solution,explanation_en,difficulty,genre,input_format,tags,normalized_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        vid,
                        problem_id,
                        version,
                        payload.title,
                        payload.statementEn,
                        Jsonb(payload.officialSolution.model_dump(mode="json")),
                        payload.explanationEn,
                        payload.difficulty.value,
                        payload.genre,
                        payload.inputFormat.value,
                        payload.tags,
                        digest,
                    ),
                )
                for ordinal, item in enumerate(payload.rubric):
                    await c.execute(
                        "INSERT INTO public.rubric_items(id,problem_version_id,ordinal,description_en,weight,is_critical,is_implicit,textual_derivation,evaluator_spec) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            item.id,
                            vid,
                            ordinal,
                            item.descriptionEn,
                            item.weight,
                            item.critical,
                            item.implicit,
                            item.textualDerivation,
                            Jsonb(item.evaluatorSpec),
                        ),
                    )
            except Exception as error:
                if "normalized_hash" in str(error) or "duplicate" in str(error).lower():
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, "DUPLICATE_PROBLEM_CONTENT"
                    ) from error
                raise
            await self._audit(
                c,
                principal.user_id,
                "problem_version_created",
                "problem_version",
                vid,
                "draft created",
            )
        result = await self.get_version(vid)
        assert result is not None
        return result

    async def replace_version(
        self,
        principal: Principal,
        version_id: str,
        payload: ProblemVersionWrite,
        expected: str,
    ) -> AdminProblemVersion:
        digest = _digest(payload)
        async with self.database.privileged() as c:
            old = await (
                await c.execute(
                    "SELECT * FROM public.problem_versions WHERE id=%s FOR UPDATE",
                    (version_id,),
                )
            ).fetchone()
            if old is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, "PROBLEM_VERSION_NOT_FOUND"
                )
            if old["state"] != "draft":
                raise HTTPException(status.HTTP_409_CONFLICT, "FROZEN_CONTENT")
            if old["normalized_hash"] != expected:
                raise HTTPException(status.HTTP_409_CONFLICT, "ETAG_MISMATCH")
            await c.execute(
                "UPDATE public.problem_versions SET title=%s,statement_en=%s,official_solution=%s,explanation_en=%s,difficulty=%s,genre=%s,input_format=%s,tags=%s,normalized_hash=%s WHERE id=%s",
                (
                    payload.title,
                    payload.statementEn,
                    Jsonb(payload.officialSolution.model_dump(mode="json")),
                    payload.explanationEn,
                    payload.difficulty.value,
                    payload.genre,
                    payload.inputFormat.value,
                    payload.tags,
                    digest,
                    version_id,
                ),
            )
            await c.execute(
                "DELETE FROM public.rubric_items WHERE problem_version_id=%s",
                (version_id,),
            )
            for ordinal, item in enumerate(payload.rubric):
                await c.execute(
                    "INSERT INTO public.rubric_items(id,problem_version_id,ordinal,description_en,weight,is_critical,is_implicit,textual_derivation,evaluator_spec) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        item.id,
                        version_id,
                        ordinal,
                        item.descriptionEn,
                        item.weight,
                        item.critical,
                        item.implicit,
                        item.textualDerivation,
                        Jsonb(item.evaluatorSpec),
                    ),
                )
            await self._audit(
                c,
                principal.user_id,
                "problem_version_replaced",
                "problem_version",
                version_id,
                "draft replaced",
            )
        result = await self.get_version(version_id)
        assert result is not None
        return result

    async def validate_version(self, principal: Principal, version_id: str) -> JobModel:
        jid = str(new_ulid())
        async with self.database.privileged() as c:
            row = await (
                await c.execute(
                    "SELECT official_solution,state FROM public.problem_versions WHERE id=%s FOR UPDATE",
                    (version_id,),
                )
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, "PROBLEM_VERSION_NOT_FOUND"
                )
            try:
                validate_canonical_schema(row["official_solution"])
            except CoreValidationError as error:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, error.code
                ) from error
            if row["state"] == "draft":
                await c.execute(
                    "UPDATE public.problem_versions SET state='validated' WHERE id=%s",
                    (version_id,),
                )
            await c.execute(
                "INSERT INTO private.jobs(id,owner_user_id,kind,payload) VALUES (%s,%s,%s,%s)",
                (
                    jid,
                    principal.user_id,
                    "admin_problem_validation",
                    Jsonb({"problemVersionId": version_id}),
                ),
            )
            await self._audit(
                c,
                principal.user_id,
                "problem_version_validated",
                "problem_version",
                version_id,
                "static validation queued",
            )
        return JobModel(id=jid, kind="admin_problem_validation", state="pending")

    async def publish_version(
        self, principal: Principal, version_id: str, payload: PublishProblem
    ) -> AdminProblemVersion:
        async with self.database.privileged() as c:
            row = await (
                await c.execute(
                    "SELECT * FROM public.problem_versions WHERE id=%s FOR UPDATE",
                    (version_id,),
                )
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, "PROBLEM_VERSION_NOT_FOUND"
                )
            approval = await (
                await c.execute(
                    "SELECT 1 FROM public.admin_approvals WHERE action='correction' AND target_id=%s AND target_digest=%s",
                    (version_id, payload.approvedTargetDigest),
                )
            ).fetchone()
            if approval is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "APPROVAL_REQUIRED")
            if row["state"] not in {"approved", "published"}:
                raise HTTPException(status.HTTP_409_CONFLICT, "VERSION_NOT_APPROVED")
            published_at = datetime(
                payload.publicationDate.year,
                payload.publicationDate.month,
                payload.publicationDate.day,
                4,
                tzinfo=ZoneInfo("Asia/Tokyo"),
            ).astimezone(UTC)
            try:
                await c.execute(
                    "INSERT INTO public.publication_calendar(publication_date,problem_id,problem_version_id,published_at) VALUES (%s,%s,%s,%s) ON CONFLICT (publication_date) DO UPDATE SET problem_version_id=excluded.problem_version_id",
                    (
                        payload.publicationDate,
                        row["problem_id"],
                        version_id,
                        published_at,
                    ),
                )
            except Exception as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "PUBLICATION_CONFLICT"
                ) from error
            await c.execute(
                "UPDATE public.problem_versions SET state='published',frozen_at=coalesce(frozen_at,now()) WHERE id=%s",
                (version_id,),
            )
            await self._audit(
                c,
                principal.user_id,
                "problem_version_published",
                "problem_version",
                version_id,
                "approved publication",
            )
        result = await self.get_version(version_id)
        assert result is not None
        return result

    async def create_notice(
        self, principal: Principal, payload: NoticeWrite, notice_id: str | None = None
    ) -> AdminNotice:
        nid = notice_id or str(new_ulid())
        vid = str(new_ulid())
        async with self.database.privileged() as c:
            if notice_id is None:
                await c.execute("INSERT INTO public.notices(id) VALUES (%s)", (nid,))
            row = await (
                await c.execute(
                    "SELECT coalesce(max(version),0)+1 AS version FROM public.notice_versions WHERE notice_id=%s",
                    (nid,),
                )
            ).fetchone()
            assert row is not None
            version = int(row["version"])
            await c.execute(
                "INSERT INTO public.notice_versions(id,notice_id,version,title_en,body_en,target_digest) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    vid,
                    nid,
                    version,
                    payload.titleEn,
                    payload.bodyEn,
                    payload.targetDigest,
                ),
            )
            await self._audit(
                c,
                principal.user_id,
                "notice_version_created",
                "notice_version",
                vid,
                "notice draft created",
            )
        return AdminNotice(
            id=nid,
            versionId=vid,
            version=version,
            state="draft",
            titleEn=payload.titleEn,
            bodyEn=payload.bodyEn,
            targetDigest=payload.targetDigest,
        )

    async def publish_notice(
        self, principal: Principal, version_id: str, digest: str
    ) -> AdminNotice:
        async with self.database.privileged() as c:
            row = await (
                await c.execute(
                    "SELECT * FROM public.notice_versions WHERE id=%s FOR UPDATE",
                    (version_id,),
                )
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, "NOTICE_VERSION_NOT_FOUND"
                )
            if row["target_digest"] != digest:
                raise HTTPException(status.HTTP_409_CONFLICT, "DIGEST_MISMATCH")
            approval = await (
                await c.execute(
                    "SELECT 1 FROM public.admin_approvals WHERE action='notice' AND target_id=%s AND target_digest=%s",
                    (version_id, digest),
                )
            ).fetchone()
            if approval is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "APPROVAL_REQUIRED")
            published = datetime.now(UTC)
            await c.execute(
                "UPDATE public.notice_versions SET state='published',published_at=%s WHERE id=%s",
                (published, version_id),
            )
            await self._audit(
                c,
                principal.user_id,
                "notice_version_published",
                "notice_version",
                version_id,
                "approved notice",
            )
            row["state"] = "published"
            row["published_at"] = published
        return AdminNotice(
            id=str(row["notice_id"]),
            versionId=str(row["id"]),
            version=row["version"],
            state=row["state"],
            titleEn=row["title_en"],
            bodyEn=row["body_en"],
            targetDigest=row["target_digest"],
            publishedAt=row["published_at"],
        )

    async def approval(self, principal: Principal, payload: ApprovalCreate) -> Approval:
        aid = str(new_ulid())
        async with self.database.privileged() as c:
            if payload.action == "correction":
                target = await (
                    await c.execute(
                        "SELECT state,normalized_hash FROM public.problem_versions WHERE id=%s",
                        (payload.targetId,),
                    )
                ).fetchone()
                if target is None or target["normalized_hash"] != payload.targetDigest:
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND, "APPROVAL_TARGET_NOT_FOUND"
                    )
                await c.execute(
                    "UPDATE public.problem_versions SET state='approved',frozen_at=coalesce(frozen_at,now()) WHERE id=%s AND state='validated'",
                    (payload.targetId,),
                )
            else:
                target = await (
                    await c.execute(
                        "SELECT target_digest,state FROM public.notice_versions WHERE id=%s",
                        (payload.targetId,),
                    )
                ).fetchone()
                if target is None or target["target_digest"] != payload.targetDigest:
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND, "APPROVAL_TARGET_NOT_FOUND"
                    )
                await c.execute(
                    "UPDATE public.notice_versions SET state='approved' WHERE id=%s AND state='draft'",
                    (payload.targetId,),
                )
            try:
                row = await (
                    await c.execute(
                        "INSERT INTO public.admin_approvals(id,actor_user_id,action,target_id,target_digest,reason) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id::text,action,target_id::text,target_digest,approved_at",
                        (
                            aid,
                            principal.user_id,
                            payload.action,
                            payload.targetId,
                            payload.targetDigest,
                            payload.reason,
                        ),
                    )
                ).fetchone()
            except Exception as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "APPROVAL_ALREADY_EXISTS"
                ) from error
            assert row is not None
            await self._audit(
                c,
                principal.user_id,
                "approval_created",
                payload.action,
                payload.targetId,
                payload.reason,
            )
        return Approval(
            id=row["id"],
            action=row["action"],
            targetId=row["target_id"],
            targetDigest=row["target_digest"],
            approvedAt=row["approved_at"],
        )

    async def batch(self, principal: Principal, month: str) -> JobModel:
        jid = str(new_ulid())
        async with self.database.privileged() as c:
            await c.execute(
                "INSERT INTO private.jobs(id,owner_user_id,kind,payload) VALUES (%s,%s,%s,%s)",
                (
                    jid,
                    principal.user_id,
                    "problem_batch_generation",
                    Jsonb({"calendarMonth": month}),
                ),
            )
            await self._audit(
                c,
                principal.user_id,
                "problem_batch_requested",
                "calendar_month",
                month,
                "bounded generation job",
            )
        return JobModel(id=jid, kind="problem_batch_generation", state="pending")

    async def posts(self, state: str, limit: int) -> list[CommunityPostModel]:
        async with self.database.privileged() as c:
            rows = await (
                await c.execute(
                    "SELECT p.id::text,p.submission_id::text,p.explanation,p.schema_snapshot,p.moderation_state,u.display_name,pv.version FROM public.posts p JOIN public.users u ON u.id=p.author_user_id JOIN public.submissions s ON s.id=p.submission_id JOIN public.problem_versions pv ON pv.id=s.problem_version_id WHERE p.moderation_state=%s ORDER BY p.created_at,p.id LIMIT %s",
                    (state, limit),
                )
            ).fetchall()
        return [
            CommunityPostModel.model_validate(
                {
                    "id": r["id"],
                    "submissionId": r["submission_id"],
                    "authorDisplayName": r["display_name"],
                    "explanation": r["explanation"],
                    "originalExplanation": r["explanation"],
                    "sourceLanguage": "en",
                    "schema": r["schema_snapshot"],
                    "moderationState": r["moderation_state"],
                    "problemVersion": r["version"],
                    "oldVersion": False,
                }
            )
            for r in rows
        ]

    async def decide_post(
        self, principal: Principal, post_id: str, decision: str, reason: str
    ) -> CommunityPostModel:
        if decision not in {"approved", "rejected"}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_POST_DECISION"
            )
        async with self.database.privileged() as c:
            row = await (
                await c.execute(
                    "SELECT p.id::text,p.submission_id::text,p.explanation,p.schema_snapshot,p.moderation_state,u.display_name,pv.version FROM public.posts p JOIN public.users u ON u.id=p.author_user_id JOIN public.submissions s ON s.id=p.submission_id JOIN public.problem_versions pv ON pv.id=s.problem_version_id WHERE p.id=%s FOR UPDATE",
                    (post_id,),
                )
            ).fetchone()
            if row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "POST_NOT_FOUND")
            await c.execute(
                "UPDATE public.posts SET moderation_state=%s,published_at=CASE WHEN %s='approved' THEN now() ELSE NULL END WHERE id=%s",
                (decision, decision, post_id),
            )
            await c.execute(
                "INSERT INTO public.moderation_decisions(id,post_id,state,jev_version,evidence) VALUES (%s,%s,%s,%s,%s)",
                (
                    str(new_ulid()),
                    post_id,
                    decision,
                    "human",
                    Jsonb({"reason": reason}),
                ),
            )
            await self._audit(
                c, principal.user_id, "post_decided", "post", post_id, reason
            )
            row["moderation_state"] = decision
        return CommunityPostModel.model_validate(
            {
                "id": row["id"],
                "submissionId": row["submission_id"],
                "authorDisplayName": row["display_name"],
                "explanation": row["explanation"],
                "originalExplanation": row["explanation"],
                "sourceLanguage": "en",
                "schema": row["schema_snapshot"],
                "moderationState": decision,
                "problemVersion": row["version"],
                "oldVersion": False,
            }
        )

    async def decide_report(
        self, principal: Principal, report_id: str, decision: str, reason: str
    ) -> ReportModel:
        if decision not in {"valid", "invalid", "resolved"}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_REPORT_DECISION"
            )
        async with self.database.privileged() as c:
            row = await (
                await c.execute(
                    "UPDATE public.reports SET state=%s WHERE id=%s RETURNING id::text,category,target_id::text,description,state,created_at",
                    (decision, report_id),
                )
            ).fetchone()
            if row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "REPORT_NOT_FOUND")
            await self._audit(
                c, principal.user_id, "report_decided", "report", report_id, reason
            )
        return ReportModel(
            id=row["id"],
            category=row["category"],
            targetId=row["target_id"],
            description=row["description"],
            state=row["state"],
            createdAt=row["created_at"],
        )

    async def entitlement(
        self, principal: Principal, payload: EntitlementChange
    ) -> Entitlement:
        async with self.database.privileged() as c:
            if payload.action == "grant":
                await c.execute(
                    "UPDATE public.entitlements SET revoked_at=now() WHERE user_id=%s AND kind='premium' AND revoked_at IS NULL",
                    (payload.userId,),
                )
                await c.execute(
                    "INSERT INTO public.entitlements(id,user_id,kind,source,valid_from,valid_until) VALUES (%s,%s,'premium','admin',now(),%s)",
                    (str(new_ulid()), payload.userId, payload.validUntil),
                )
                premium = True
                valid_until = payload.validUntil
            else:
                await c.execute(
                    "UPDATE public.entitlements SET revoked_at=now() WHERE user_id=%s AND kind='premium' AND revoked_at IS NULL",
                    (payload.userId,),
                )
                premium = False
                valid_until = None
            await self._audit(
                c,
                principal.user_id,
                "entitlement_changed",
                "user",
                payload.userId,
                payload.reason,
            )
        return Entitlement(premium=premium, validUntil=valid_until)
