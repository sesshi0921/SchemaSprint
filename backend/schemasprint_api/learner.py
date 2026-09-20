"""Learner-facing API models and database operations.

The module deliberately keeps all learner reads behind ``Database.as_user`` so
PostgreSQL RLS remains the second authorization boundary.  Mutating operations
use the service connection only for immutable server-owned records and always
include the authenticated internal user id in their predicates.
"""

# ruff: noqa: E501

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import JevMode, Settings
from .core import (
    Assessment,
    CoreValidationError,
    compute_assessment,
    validate_canonical_schema,
)
from .database import Database
from .problems import Locale, ProblemDetail
from .security import Principal


class Difficulty(StrEnum):
    EASY = "easy"
    MID = "mid"
    HARD = "hard"


class InputFormat(StrEnum):
    GUI = "gui"
    MERMAID = "mermaid"
    DDL = "ddl"
    DBML = "dbml"
    MIXED = "mixed"


class ProblemStatus(StrEnum):
    PASSED = "passed"
    NOT_PASSED = "not_passed"
    UNSUBMITTED = "unsubmitted"


class CanonicalSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal[1]
    tables: list[dict[str, Any]] = Field(max_length=200)
    relationships: list[dict[str, Any]] = Field(max_length=2000)
    enums: list[dict[str, Any]] | None = Field(default=None, max_length=200)
    views: list[dict[str, Any]] | None = Field(default=None, max_length=200)
    triggers: list[dict[str, Any]] | None = Field(default=None, max_length=200)
    policies: list[dict[str, Any]] | None = Field(default=None, max_length=500)
    partitions: list[dict[str, Any]] | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_engine_schema(self) -> Self:
        try:
            validate_canonical_schema(
                self.model_dump(exclude_none=True)  # type: ignore[arg-type]
            )
        except CoreValidationError as error:
            raise ValueError(error.code) from error
        return self


class EditorSourcesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ddl: str | None = Field(default=None, max_length=1_048_576)
    mermaid: str | None = Field(default=None, max_length=1_048_576)
    dbml: str | None = Field(default=None, max_length=1_048_576)
    activeFormat: InputFormat | None = None
    warnings: list[str] | None = Field(default=None, max_length=500)


class DraftWriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonicalSchema: CanonicalSchemaModel
    editorSources: EditorSourcesModel
    layout: dict[str, Any]


class DraftModel(DraftWriteModel):
    problemId: str = Field(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
    revision: int = Field(ge=1)
    updatedAt: datetime


class StaticAnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parserVersion: str = Field(min_length=1, max_length=100)
    diagnostics: list[dict[str, Any]] = Field(max_length=2000)


class SubmissionCreateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problemId: str = Field(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
    problemVersionId: str = Field(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
    canonicalSchema: CanonicalSchemaModel
    editorSources: EditorSourcesModel
    staticAnalysis: StaticAnalysisModel


class AssessmentRequirementModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubricItemId: str
    decision: Literal["satisfied", "not_met"]
    source: Literal["static", "jev"]
    confidence: float | None = Field(default=None, ge=0, le=100)
    impact: str


class AssessmentResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=100)
    exactFull: bool
    passed: bool
    contradiction: bool
    confidence: float = Field(ge=0, le=100)
    requirements: list[AssessmentRequirementModel] = Field(max_length=2000)


class SubmissionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    problemId: str = Field(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
    problemVersionId: str = Field(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
    state: Literal["pending", "assessed", "failed"]
    canonicalSchema: CanonicalSchemaModel
    result: AssessmentResultModel | None = None
    failureCode: str | None = None
    createdAt: datetime


class ProblemSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int
    title: str
    difficulty: Difficulty
    genre: str
    inputFormat: InputFormat
    tags: list[str]
    publicationDate: date
    passed: bool
    submitted: bool
    translationStatus: Literal["source", "translated", "pending", "unavailable"]


class ProblemPageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProblemSummaryModel]
    nextCursor: str | None = None


class ProfileEntitlementModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premium: bool
    validUntil: datetime | None = None
    billingEnabled: Literal[False] = False
    adsEnabled: Literal[False] = False


class ProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    displayName: str
    locale: Locale
    theme: Literal["system", "light", "dark"]
    roles: list[Literal["learner", "moderator", "admin", "owner"]]
    entitlement: ProfileEntitlementModel


class ProfilePatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    displayName: str | None = Field(default=None, min_length=1, max_length=64)
    locale: Locale | None = None
    theme: Literal["system", "light", "dark"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("profile patch cannot be empty")
        return self


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["terms", "privacy", "community"]
    version: int
    content: str
    requiredFrom: datetime
    acknowledged: bool


class DashboardModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uniquePassed: int = Field(ge=0)
    byDifficulty: dict[str, int]
    byWeekday: dict[str, int]
    calendar: list[dict[str, Any]]


class NoticeItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    versionId: str
    title: str
    body: str
    publishedAt: datetime
    read: bool


class NoticePageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NoticeItemModel]
    unreadCount: int = Field(ge=0)
    nextCursor: str | None = None


class _Cursor:
    """Signed cursor bound to the normalized request filters."""

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def encode(self, payload: Mapping[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()[:16]
        return base64.urlsafe_b64encode(raw + b"." + signature).decode().rstrip("=")

    def decode(self, value: str, filters: Mapping[str, Any]) -> dict[str, Any]:
        try:
            padded = value + "=" * (-len(value) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode())
            raw, signature = decoded.rsplit(b".", 1)
            expected = hmac.new(self._secret, raw, hashlib.sha256).digest()[:16]
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("v") != 1:
                raise ValueError
            digest = hashlib.sha256(
                json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if payload.get("f") != digest:
                raise ValueError
            return payload
        except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "INVALID_CURSOR"
            ) from error

    def with_filter_digest(
        self, position: Mapping[str, Any], filters: Mapping[str, Any]
    ) -> str:
        digest = hashlib.sha256(
            json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return self.encode({"v": 1, "f": digest, **dict(position)})


def _dump(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _schema(value: Mapping[str, Any]) -> CanonicalSchemaModel:
    return CanonicalSchemaModel.model_validate(value)


def _problem_summary(row: Mapping[str, Any]) -> ProblemSummaryModel:
    return ProblemSummaryModel.model_validate(
        {
            "id": row["id"],
            "version": row["version"],
            "title": row["title"],
            "difficulty": row["difficulty"],
            "genre": row["genre"],
            "inputFormat": row["input_format"],
            "tags": list(row["tags"] or []),
            "publicationDate": row["publication_date"],
            "passed": bool(row["passed"]),
            "submitted": bool(row["submitted"]),
            "translationStatus": row["translation_status"],
        }
    )


@dataclass(slots=True)
class LearnerRepository:
    database: Database
    settings: Settings

    async def list_problems(
        self,
        principal: Principal,
        *,
        cursor: str | None,
        limit: int,
        q: str | None,
        difficulty: Difficulty | None,
        genre: str | None,
        input_format: InputFormat | None,
        problem_status: ProblemStatus | None,
        published_from: date | None,
        published_to: date | None,
        locale: Locale,
    ) -> ProblemPageModel:
        filters: dict[str, Any] = {
            "q": q,
            "difficulty": difficulty.value if difficulty else None,
            "genre": genre,
            "inputFormat": input_format.value if input_format else None,
            "status": problem_status.value if problem_status else None,
            "publishedFrom": published_from.isoformat() if published_from else None,
            "publishedTo": published_to.isoformat() if published_to else None,
            "locale": locale.value,
        }
        position: dict[str, Any] | None = None
        if cursor:
            position = _Cursor(self.settings.session_pepper.get_secret_value()).decode(
                cursor, filters
            )
        predicates = ["pc.published_at <= now()"]
        params: list[Any] = []
        if q:
            predicates.append(
                "to_tsvector('english', pv.title || ' ' || pv.statement_en) @@ plainto_tsquery('english', %s)"
            )
            params.append(q)
        if difficulty:
            predicates.append("pv.difficulty = %s")
            params.append(difficulty.value)
        if genre:
            predicates.append("pv.genre = %s")
            params.append(genre)
        if input_format:
            predicates.append("pv.input_format = %s")
            params.append(input_format.value)
        if published_from:
            predicates.append("pc.publication_date >= %s")
            params.append(published_from)
        if published_to:
            predicates.append("pc.publication_date <= %s")
            params.append(published_to)
        if problem_status is ProblemStatus.PASSED:
            predicates.append(
                "EXISTS (SELECT 1 FROM public.submissions s JOIN public.submission_results sr ON sr.submission_id=s.id WHERE s.user_id=public.current_user_id() AND s.problem_id=p.id AND sr.passed)"
            )
        elif problem_status is ProblemStatus.NOT_PASSED:
            predicates.append(
                "EXISTS (SELECT 1 FROM public.submissions s WHERE s.user_id=public.current_user_id() AND s.problem_id=p.id)"
            )
            predicates.append(
                "NOT EXISTS (SELECT 1 FROM public.submissions s JOIN public.submission_results sr ON sr.submission_id=s.id WHERE s.user_id=public.current_user_id() AND s.problem_id=p.id AND sr.passed)"
            )
        elif problem_status is ProblemStatus.UNSUBMITTED:
            predicates.append(
                "NOT EXISTS (SELECT 1 FROM public.submissions s WHERE s.user_id=public.current_user_id() AND s.problem_id=p.id)"
            )
        if position:
            predicates.append("(pc.publication_date, p.id) < (%s, %s)")
            params.extend([position.get("date"), position.get("id")])
        # Placeholders in the SELECT precede the filter placeholders.
        params = [locale.value, locale.value, *params, limit + 1]
        query = f"""
            SELECT p.id::text AS id, pv.version, pv.title, pv.difficulty::text,
                   pv.genre, pv.input_format, pv.tags, pc.publication_date,
                   EXISTS (SELECT 1 FROM public.submissions s
                           WHERE s.user_id = public.current_user_id()
                             AND s.problem_id = p.id) AS submitted,
                   EXISTS (SELECT 1 FROM public.submissions s
                           JOIN public.submission_results sr ON sr.submission_id = s.id
                           WHERE s.user_id = public.current_user_id()
                             AND s.problem_id = p.id AND sr.passed) AS passed,
                   CASE WHEN %s = 'en' THEN 'source'
                        WHEN EXISTS (SELECT 1 FROM public.translation_cache tc
                           WHERE tc.content_kind='problem_statement'
                             AND tc.content_id=pv.id AND tc.content_version=pv.version
                             AND tc.locale=%s AND tc.owner_user_id IS NULL)
                        THEN 'translated' ELSE 'unavailable' END AS translation_status
            FROM public.publication_calendar pc
            JOIN public.problems p ON p.id=pc.problem_id
            JOIN public.problem_versions pv ON pv.id=pc.problem_version_id
            WHERE {" AND ".join(predicates)}
            ORDER BY pc.publication_date DESC, p.id DESC
            LIMIT %s
        """
        async with self.database.as_user(principal) as connection:
            rows = await (await connection.execute(query, params)).fetchall()
        items = [_problem_summary(row) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = _Cursor(
                self.settings.session_pepper.get_secret_value()
            ).with_filter_digest(
                {"date": last["publication_date"].isoformat(), "id": last["id"]},
                filters,
            )
        return ProblemPageModel(items=items, nextCursor=next_cursor)

    async def detail(
        self,
        principal: Principal,
        problem_id: str,
        locale: Locale,
        version: int | None,
    ) -> ProblemDetail | None:
        version_clause = (
            "pc.problem_version_id = pv.id" if version is None else "pv.version = %s"
        )
        query = f"""
            SELECT p.id::text AS id, pv.id::text AS problem_version_id, pv.version,
                   pv.title, pv.official_solution AS official_answer,
                   pv.difficulty::text AS difficulty, pv.genre, pv.input_format,
                   pv.tags, pc.publication_date,
                   COALESCE(st.translated_text, pv.statement_en) AS statement,
                   COALESCE(et.translated_text, pv.explanation_en) AS explanation,
                   EXISTS (SELECT 1 FROM public.submissions s WHERE s.user_id=public.current_user_id()
                           AND s.problem_id=p.id AND s.problem_version_id=pv.id) AS submitted,
                   EXISTS (SELECT 1 FROM public.submissions s JOIN public.submission_results sr ON sr.submission_id=s.id
                           WHERE s.user_id=public.current_user_id() AND s.problem_id=p.id
                             AND s.problem_version_id=pv.id AND sr.passed) AS passed,
                   CASE WHEN %s='en' THEN 'source'
                        WHEN st.translated_text IS NOT NULL AND et.translated_text IS NOT NULL THEN 'translated'
                        ELSE 'unavailable' END AS translation_status,
                   COALESCE(jsonb_agg(jsonb_build_object('id',ri.id::text,
                       'description',ri.description_en,'weight',ri.weight,
                       'critical',ri.is_critical,'implicit',ri.is_implicit)
                       ORDER BY ri.ordinal) FILTER (WHERE ri.id IS NOT NULL), '[]'::jsonb) AS rubric_summary
            FROM public.publication_calendar pc
            JOIN public.problems p ON p.id=pc.problem_id
            JOIN public.problem_versions pv ON pv.problem_id=p.id
            LEFT JOIN public.rubric_items ri ON ri.problem_version_id=pv.id
            LEFT JOIN public.translation_cache st ON st.content_kind='problem_statement'
              AND st.content_id=pv.id AND st.content_version=pv.version
              AND st.locale=%s AND st.owner_user_id IS NULL
            LEFT JOIN public.translation_cache et ON et.content_kind='problem_explanation'
              AND et.content_id=pv.id AND et.content_version=pv.version
              AND et.locale=%s AND et.owner_user_id IS NULL
            WHERE p.id=%s AND pv.state IN ('published','retired')
              AND pc.published_at <= now() AND {version_clause}
            GROUP BY p.id,pv.id,pv.version,pv.title,pv.official_solution,pv.difficulty,
                     pv.genre,pv.input_format,pv.tags,pc.publication_date,
                     st.translated_text,et.translated_text
        """
        # Reorder params to match the SQL's first placeholder in the select.
        query_params: list[Any] = [locale.value, locale.value, locale.value, problem_id]
        if version is not None:
            query_params.append(version)
        async with self.database.as_user(principal) as connection:
            row = await (await connection.execute(query, query_params)).fetchone()
        if row is None:
            return None
        return ProblemDetail.model_validate(
            {
                "id": row["id"],
                "version": row["version"],
                "title": row["title"],
                "difficulty": row["difficulty"],
                "genre": row["genre"],
                "inputFormat": row["input_format"],
                "tags": list(row["tags"] or []),
                "publicationDate": row["publication_date"],
                "passed": bool(row["passed"]),
                "submitted": bool(row["submitted"]),
                "translationStatus": row["translation_status"],
                "problemVersionId": row["problem_version_id"],
                "statement": row["statement"],
                "officialAnswer": row["official_answer"],
                "explanation": row["explanation"],
                "sourceLanguage": "en",
                "requestedLocale": locale,
                "rubricSummary": row["rubric_summary"],
            }
        )

    async def get_draft(
        self, principal: Principal, problem_id: str
    ) -> DraftModel | None:
        query = """
            SELECT problem_id::text, revision, canonical_schema, editor_sources,
                   layout, updated_at
            FROM public.workspaces
            WHERE user_id=public.current_user_id() AND problem_id=%s
        """
        async with self.database.as_user(principal) as connection:
            row = await (await connection.execute(query, (problem_id,))).fetchone()
        if row is None:
            return None
        return DraftModel.model_validate(
            {
                "problemId": row["problem_id"],
                "revision": row["revision"],
                "canonicalSchema": row["canonical_schema"],
                "editorSources": row["editor_sources"],
                "layout": row["layout"],
                "updatedAt": row["updated_at"],
            }
        )

    async def put_draft(
        self,
        principal: Principal,
        problem_id: str,
        expected_revision: int,
        draft: DraftWriteModel,
    ) -> DraftModel:
        values = _dump(draft)
        query = """
            INSERT INTO public.workspaces
                (user_id, problem_id, canonical_schema, editor_sources, layout)
            VALUES (public.current_user_id(), %s, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT (user_id, problem_id) DO UPDATE SET
                canonical_schema=EXCLUDED.canonical_schema,
                editor_sources=EXCLUDED.editor_sources,
                layout=EXCLUDED.layout,
                revision=public.workspaces.revision + 1
            WHERE public.workspaces.revision = %s
            RETURNING problem_id::text, revision, canonical_schema, editor_sources,
                      layout, updated_at
        """
        async with self.database.as_user(principal) as connection:
            row = await (
                await connection.execute(
                    query,
                    (
                        problem_id,
                        json.dumps(values["canonicalSchema"], separators=(",", ":")),
                        json.dumps(values["editorSources"], separators=(",", ":")),
                        json.dumps(values["layout"], separators=(",", ":")),
                        expected_revision,
                    ),
                )
            ).fetchone()
            if row is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "DRAFT_REVISION_CONFLICT")
        return DraftModel.model_validate(
            {
                "problemId": row["problem_id"],
                "revision": row["revision"],
                "canonicalSchema": row["canonical_schema"],
                "editorSources": row["editor_sources"],
                "layout": row["layout"],
                "updatedAt": row["updated_at"],
            }
        )

    async def delete_draft(
        self, principal: Principal, problem_id: str, expected_revision: int
    ) -> None:
        async with self.database.as_user(principal) as connection:
            deleted = await (
                await connection.execute(
                    """
                    DELETE FROM public.workspaces
                    WHERE user_id=public.current_user_id()
                      AND problem_id=%s AND revision=%s
                    RETURNING problem_id
                    """,
                    (problem_id, expected_revision),
                )
            ).fetchone()
            if deleted is None:
                current = await (
                    await connection.execute(
                        """
                        SELECT revision FROM public.workspaces
                        WHERE user_id=public.current_user_id() AND problem_id=%s
                        """,
                        (problem_id,),
                    )
                ).fetchone()
                if current is not None:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, "DRAFT_REVISION_CONFLICT"
                    )

    async def _rubric(
        self, principal: Principal, problem_version_id: str
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id::text, ordinal, description_en, weight,
                   is_critical AS critical, is_implicit AS implicit,
                   textual_derivation, evaluator_spec
            FROM public.rubric_items WHERE problem_version_id=%s ORDER BY ordinal
        """
        async with self.database.as_user(principal) as connection:
            rows = await (
                await connection.execute(query, (problem_version_id,))
            ).fetchall()
        return [dict(row) for row in rows]

    async def _problem_snapshot(
        self, principal: Principal, problem_id: str, problem_version_id: str
    ) -> dict[str, Any] | None:
        """Read the exact published version used by this submission."""
        query = """
            SELECT p.id::text AS problem_id, pv.id::text AS problem_version_id,
                   pv.version, pv.title, pv.statement_en, pv.official_solution,
                   pv.explanation_en, pv.difficulty::text AS difficulty,
                   pv.genre, pv.input_format, pv.tags
            FROM public.problems p
            JOIN public.problem_versions pv ON pv.problem_id=p.id
            WHERE p.id=%s AND pv.id=%s
        """
        async with self.database.as_user(principal) as connection:
            row = await (
                await connection.execute(query, (problem_id, problem_version_id))
            ).fetchone()
        if row is None:
            return None
        return {
            "problemId": row["problem_id"],
            "problemVersionId": row["problem_version_id"],
            "version": row["version"],
            "title": row["title"],
            "statementEn": row["statement_en"],
            "officialSolution": row["official_solution"],
            "explanationEn": row["explanation_en"],
            "difficulty": row["difficulty"],
            "genre": row["genre"],
            "inputFormat": row["input_format"],
            "tags": list(row["tags"] or []),
        }

    @staticmethod
    def _static_decisions(
        schema: Mapping[str, Any], rubric: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        """Evaluate only explicit, objective evaluator specs.

        Unknown specs are deliberately ``not_met`` in the development stub;
        this avoids presenting a semantic guess as a successful grade.
        """
        tables = {str(table.get("id")): table for table in schema.get("tables", [])}
        table_names = {str(table.get("name")) for table in schema.get("tables", [])}
        relationships = schema.get("relationships", [])
        results: list[dict[str, Any]] = []
        for item in rubric:
            spec = item.get("evaluator_spec")
            satisfied = False
            if isinstance(spec, Mapping):
                required_table = spec.get("requiredTable") or spec.get("tableId")
                required_column = spec.get("requiredColumn")
                required_relationship = spec.get("requiredRelationship")
                if required_table is not None:
                    table = tables.get(str(required_table))
                    satisfied = table is not None or str(required_table) in table_names
                    if satisfied and required_column is not None:
                        columns = table.get("columns", []) if table else []
                        satisfied = any(
                            str(col.get("id")) == str(required_column)
                            or str(col.get("name")) == str(required_column)
                            for col in columns
                        )
                elif isinstance(required_relationship, Mapping):
                    satisfied = any(
                        all(rel.get(k) == v for k, v in required_relationship.items())
                        for rel in relationships
                        if isinstance(rel, Mapping)
                    )
                elif spec.get("always") is True:
                    satisfied = True
            results.append(
                {
                    "rubricItemId": str(item["id"]),
                    "decision": "satisfied" if satisfied else "not_met",
                }
            )
        return results

    @staticmethod
    def _server_static_analysis(
        schema: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        """Return the deterministic, server-owned preprocessing snapshot.

        The client-provided diagnostics are useful for editor UX only.  They
        are never used for score or pass computation; the canonical schema has
        already crossed the Rust validation boundary before this method runs.
        """
        return {
            "parserVersion": "rust-static-0.1",
            "source": "server",
            "diagnostics": [],
            "decisionCount": len(decisions),
            "schemaDigest": hashlib.sha256(
                json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }

    async def create_submission(
        self,
        principal: Principal,
        payload: SubmissionCreateModel,
        jev_mode: JevMode,
        idempotency_key: UUID,
    ) -> SubmissionModel:
        request_digest = hashlib.sha256(
            json.dumps(_dump(payload), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        # The HTTP idempotency table is a replay cache.  This unique,
        # user-bound row is the authoritative database-level duplicate guard.
        async with self.database.privileged() as connection:
            existing = await (
                await connection.execute(
                    """
                    SELECT id::text, request_digest
                    FROM public.submissions
                    WHERE user_id=%s AND idempotency_key=%s
                    FOR UPDATE
                    """,
                    (principal.user_id, idempotency_key),
                )
            ).fetchone()
        if existing is not None:
            if existing["request_digest"] != request_digest:
                raise HTTPException(status.HTTP_409_CONFLICT, "IDEMPOTENCY_KEY_REUSED")
            replay = await self.get_submission(principal, existing["id"])
            if replay is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "SUBMISSION_NOT_VISIBLE")
            return replay

        rubric = await self._rubric(principal, payload.problemVersionId)
        if not rubric:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROBLEM_VERSION_NOT_FOUND")
        problem_snapshot = await self._problem_snapshot(
            principal, payload.problemId, payload.problemVersionId
        )
        if problem_snapshot is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROBLEM_VERSION_NOT_FOUND")
        schema_payload = payload.canonicalSchema.model_dump(exclude_none=True)
        static_decisions = self._static_decisions(schema_payload, rubric)
        static_analysis_snapshot = self._server_static_analysis(
            schema_payload, static_decisions
        )
        rubric_snapshot = [
            {
                "id": str(item["id"]),
                "ordinal": item["ordinal"],
                "descriptionEn": item["description_en"],
                "weight": item["weight"],
                "critical": bool(item["critical"]),
                "implicit": bool(item["implicit"]),
                "textualDerivation": item.get("textual_derivation"),
                "evaluatorSpec": item["evaluator_spec"],
            }
            for item in rubric
        ]
        contradiction = any(
            isinstance(item.get("evaluator_spec"), Mapping)
            and item["evaluator_spec"].get("contradiction") is True
            and decision["decision"] == "satisfied"
            for item, decision in zip(rubric, static_decisions, strict=True)
        )
        assessment_snapshot: dict[str, Any]
        assessment: Assessment | None = None
        result: AssessmentResultModel | None = None
        state: Literal["pending", "assessed", "failed"] = "failed"
        failure_code: str | None = None
        if jev_mode is not JevMode.STUB:
            # No provider adapter exists in this service yet.  Persist a
            # definitive failure instead of returning a job that can never
            # resolve.  A future worker may add a real external adapter.
            result = None
            state = "failed"
            failure_code = "JEV_UNAVAILABLE"
            assessment_snapshot = {
                "state": state,
                "failureCode": failure_code,
                "staticDecisions": static_decisions,
                "jevMode": jev_mode.value,
                "staticAnalysis": static_analysis_snapshot,
                "rubric": rubric_snapshot,
                "problemVersionId": payload.problemVersionId,
            }
        else:
            try:
                assessment = compute_assessment(
                    [
                        {
                            "id": str(item["id"]),
                            "weight": int(item["weight"]),
                            "critical": bool(item["critical"]),
                            "implicit": bool(item["implicit"]),
                        }
                        for item in rubric
                    ],
                    static_decisions,
                    contradiction,
                )
            except CoreValidationError as error:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, error.code
                ) from error
            assert assessment is not None
            state = "assessed"
            result = AssessmentResultModel(
                score=assessment.display_tenths / 10,
                exactFull=assessment.exact_full,
                passed=assessment.passed,
                contradiction=contradiction,
                confidence=100,
                requirements=[
                    AssessmentRequirementModel(
                        rubricItemId=decision["rubricItemId"],
                        decision=decision["decision"],
                        source="static",
                        confidence=None,
                        impact="deterministic development stub",
                    )
                    for decision in static_decisions
                ],
            )
            assessment_snapshot = {
                "state": state,
                "satisfiedWeight": assessment.satisfied_weight,
                "totalWeight": assessment.total_weight,
                "exactFull": assessment.exact_full,
                "passed": assessment.passed,
                "contradiction": contradiction,
                "requirements": [
                    item.model_dump(mode="json") for item in result.requirements
                ],
                "jevMode": jev_mode.value,
                "staticAnalysis": static_analysis_snapshot,
                "rubric": rubric_snapshot,
                "problemVersionId": payload.problemVersionId,
            }
        submission_id = str(__import__("ulid").new())
        async with self.database.privileged() as connection:
            row = await (
                await connection.execute(
                    """
                    INSERT INTO public.submissions
                      (id,user_id,problem_id,problem_version_id,idempotency_key,
                       request_digest,canonical_schema,editor_sources,
                       problem_snapshot,rubric_snapshot,static_analysis_snapshot,
                       assessment_snapshot,failure_code,engine_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                            %s::jsonb,%s::jsonb,%s,%s)
                    ON CONFLICT (user_id, idempotency_key) DO NOTHING
                    RETURNING id::text, problem_id::text, problem_version_id::text,
                              canonical_schema, created_at
                    """,
                    (
                        submission_id,
                        principal.user_id,
                        payload.problemId,
                        payload.problemVersionId,
                        idempotency_key,
                        request_digest,
                        json.dumps(schema_payload, separators=(",", ":")),
                        json.dumps(_dump(payload.editorSources), separators=(",", ":")),
                        json.dumps(problem_snapshot, separators=(",", ":")),
                        json.dumps(rubric_snapshot, separators=(",", ":")),
                        json.dumps(static_analysis_snapshot, separators=(",", ":")),
                        json.dumps(assessment_snapshot, separators=(",", ":")),
                        failure_code,
                        "rust-static-0.1",
                    ),
                )
            ).fetchone()
            if row is None:
                duplicate = await (
                    await connection.execute(
                        """
                        SELECT id::text, request_digest
                        FROM public.submissions
                        WHERE user_id=%s AND idempotency_key=%s
                        FOR UPDATE
                        """,
                        (principal.user_id, idempotency_key),
                    )
                ).fetchone()
                if duplicate is None:
                    raise HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "SUBMISSION_NOT_CREATED",
                    )
                if duplicate["request_digest"] != request_digest:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, "IDEMPOTENCY_KEY_REUSED"
                    )
                replay_id = duplicate["id"]
            else:
                replay_id = None
            if replay_id is None and result is not None:
                assert row is not None
                assert assessment is not None
                await connection.execute(
                    """
                    INSERT INTO public.submission_results
                      (submission_id,user_id,problem_version_id,satisfied_weight,
                       total_weight,passed,has_contradiction,confidence,numerator,
                       denominator,display_tenths,exact_full,jev_version,static_output,
                       jev_output)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                    """,
                    (
                        row["id"],
                        principal.user_id,
                        payload.problemVersionId,
                        assessment.satisfied_weight,
                        assessment.total_weight,
                        assessment.passed,
                        contradiction,
                        100,
                        assessment.numerator,
                        assessment.denominator,
                        assessment.display_tenths,
                        assessment.exact_full,
                        "stub",
                        json.dumps({"decisions": static_decisions}),
                        json.dumps({"mode": "stub"}),
                    ),
                )
            if replay_id is None and result is not None:
                assert row is not None
                for decision in static_decisions:
                    await connection.execute(
                        """
                        INSERT INTO public.requirement_results
                          (submission_id,rubric_item_id,decision,source,confidence,impact)
                        VALUES (%s,%s,%s,'static',NULL,%s)
                        """,
                        (
                            row["id"],
                            decision["rubricItemId"],
                            decision["decision"],
                            "deterministic development stub",
                        ),
                    )
        if replay_id is not None:
            replay = await self.get_submission(principal, replay_id)
            if replay is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "SUBMISSION_NOT_VISIBLE")
            return replay
        assert row is not None
        return SubmissionModel(
            id=row["id"],
            problemId=row["problem_id"],
            problemVersionId=row["problem_version_id"],
            state=state,
            canonicalSchema=_schema(schema_payload),
            result=result,
            failureCode=failure_code,
            createdAt=row["created_at"],
        )

    async def get_submission(
        self, principal: Principal, submission_id: str
    ) -> SubmissionModel | None:
        query = """
            SELECT s.id::text, s.problem_id::text, s.problem_version_id::text,
                   s.canonical_schema, s.created_at, s.assessment_snapshot,
                   s.failure_code,
                   sr.satisfied_weight, sr.total_weight, sr.passed,
                   sr.has_contradiction, sr.confidence, sr.numerator,
                   sr.denominator, sr.display_tenths, sr.exact_full, sr.jev_version
            FROM public.submissions s
            LEFT JOIN public.submission_results sr ON sr.submission_id=s.id
            WHERE s.id=%s AND s.user_id=public.current_user_id()
        """
        async with self.database.as_user(principal) as connection:
            row = await (await connection.execute(query, (submission_id,))).fetchone()
            if row is None:
                return None
            req_rows = await (
                await connection.execute(
                    """
                    SELECT rubric_item_id::text, decision::text, source,
                           confidence, impact
                    FROM public.requirement_results WHERE submission_id=%s
                    ORDER BY rubric_item_id
                    """,
                    (submission_id,),
                )
            ).fetchall()
        result = None
        snapshot = row["assessment_snapshot"] or {}
        state_value = snapshot.get("state") if isinstance(snapshot, Mapping) else None
        state: Literal["pending", "assessed", "failed"] = (
            state_value
            if state_value in {"pending", "assessed", "failed"}
            else "pending"
        )
        if row["satisfied_weight"] is not None:
            state = "assessed"
            result = AssessmentResultModel(
                score=float(row["display_tenths"]) / 10,
                exactFull=bool(row["exact_full"]),
                passed=bool(row["passed"]),
                contradiction=bool(row["has_contradiction"]),
                confidence=float(row["confidence"]),
                requirements=[
                    AssessmentRequirementModel(
                        rubricItemId=r["rubric_item_id"],
                        decision=r["decision"],
                        source=r["source"],
                        confidence=float(r["confidence"])
                        if r["confidence"] is not None
                        else None,
                        impact=r["impact"],
                    )
                    for r in req_rows
                ],
            )
        return SubmissionModel(
            id=row["id"],
            problemId=row["problem_id"],
            problemVersionId=row["problem_version_id"],
            state=state,
            canonicalSchema=_schema(row["canonical_schema"]),
            result=result,
            failureCode=row["failure_code"]
            or (snapshot.get("failureCode") if isinstance(snapshot, Mapping) else None),
            createdAt=row["created_at"],
        )

    async def dashboard(
        self, principal: Principal, from_date: date | None, to_date: date | None
    ) -> DashboardModel:
        from_date = from_date or date.min
        to_date = to_date or date.max
        if from_date > to_date:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_DATE_RANGE"
            )
        async with self.database.as_user(principal) as connection:
            rows = await (
                await connection.execute(
                    """
                    SELECT pc.publication_date, p.id::text AS problem_id,
                           pv.difficulty::text AS difficulty,
                           lower(to_char(pc.publication_date, 'FMDay')) AS weekday
                    FROM public.submissions s
                    JOIN public.submission_results sr ON sr.submission_id=s.id AND sr.passed
                    JOIN public.problems p ON p.id=s.problem_id
                    JOIN public.publication_calendar pc ON pc.problem_id=p.id
                    JOIN public.problem_versions pv ON pv.id=pc.problem_version_id
                    WHERE s.user_id=public.current_user_id()
                      AND pc.publication_date BETWEEN %s AND %s
                    GROUP BY pc.publication_date,p.id,pv.difficulty
                    ORDER BY pc.publication_date
                    """,
                    (from_date, to_date),
                )
            ).fetchall()
        by_difficulty: dict[str, int] = {}
        by_weekday: dict[str, int] = {}
        calendar: dict[date, set[str]] = {}
        for row in rows:
            by_difficulty[row["difficulty"]] = (
                by_difficulty.get(row["difficulty"], 0) + 1
            )
            by_weekday[row["weekday"]] = by_weekday.get(row["weekday"], 0) + 1
            calendar.setdefault(row["publication_date"], set()).add(row["problem_id"])
        return DashboardModel(
            uniquePassed=len({item for values in calendar.values() for item in values}),
            byDifficulty=by_difficulty,
            byWeekday=by_weekday,
            calendar=[
                {"publicationDate": day.isoformat(), "passedProblemIds": sorted(ids)}
                for day, ids in sorted(calendar.items())
            ],
        )

    async def policies(self, principal: Principal) -> list[PolicyModel]:
        query = """
            SELECT pv.id::text, pv.kind, pv.version, pv.content_en, pv.required_from,
                   EXISTS (SELECT 1 FROM public.policy_acknowledgements pa
                           WHERE pa.user_id=public.current_user_id() AND pa.policy_version_id=pv.id)
                   AS acknowledged
            FROM public.policy_versions pv
            JOIN (SELECT kind, max(version) AS version FROM public.policy_versions
                  WHERE required_from <= now() GROUP BY kind) latest
              ON latest.kind=pv.kind AND latest.version=pv.version
            ORDER BY pv.kind
        """
        async with self.database.as_user(principal) as connection:
            rows = await (await connection.execute(query)).fetchall()
        return [
            PolicyModel.model_validate(
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "version": row["version"],
                    "content": row["content_en"],
                    "requiredFrom": row["required_from"],
                    "acknowledged": row["acknowledged"],
                }
            )
            for row in rows
        ]

    async def profile(self, principal: Principal) -> ProfileModel | None:
        query = """
            SELECT u.id::text, u.display_name, u.locale, u.theme,
                   coalesce(array_agg(r.role::text) FILTER (WHERE r.role IS NOT NULL), ARRAY[]::text[]) AS roles,
                   e.valid_until, e.user_id IS NOT NULL AS premium
            FROM public.users u
            LEFT JOIN public.role_grants r ON r.user_id=u.id
            LEFT JOIN LATERAL (
              SELECT user_id, valid_until FROM public.entitlements
              WHERE user_id=u.id AND kind='premium' AND valid_from <= now()
                AND (valid_until IS NULL OR valid_until > now()) AND revoked_at IS NULL
              ORDER BY valid_from DESC LIMIT 1
            ) e ON true
            WHERE u.id=public.current_user_id()
            GROUP BY u.id,e.user_id,e.valid_until
        """
        async with self.database.as_user(principal) as connection:
            row = await (await connection.execute(query)).fetchone()
        if row is None:
            return None
        # Every authenticated learner has the base learner capability; the
        # table stores only elevated grants.
        roles = sorted({"learner", *(str(item) for item in row["roles"])})
        return ProfileModel.model_validate(
            {
                "id": row["id"],
                "displayName": row["display_name"],
                "locale": row["locale"],
                "theme": row["theme"],
                "roles": roles,
                "entitlement": {
                    "premium": bool(row["premium"]),
                    "validUntil": row["valid_until"],
                    "billingEnabled": False,
                    "adsEnabled": False,
                },
            }
        )

    async def update_profile(
        self,
        principal: Principal,
        *,
        display_name: str | None,
        locale: Locale | None,
        theme: str | None,
    ) -> ProfileModel:
        assignments: list[str] = []
        params: list[Any] = []
        if display_name is not None:
            assignments.append("display_name=%s")
            params.append(display_name)
        if locale is not None:
            assignments.append("locale=%s")
            params.append(locale.value)
        if theme is not None:
            assignments.append("theme=%s")
            params.append(theme)
        assignments.append("updated_at=now()")
        params.append(principal.user_id)
        async with self.database.as_user(principal) as connection:
            await connection.execute(
                f"UPDATE public.users SET {', '.join(assignments)} WHERE id=%s",
                params,
            )
        result = await self.profile(principal)
        if result is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROFILE_NOT_FOUND")
        return result

    async def list_notices(
        self, principal: Principal, *, cursor: str | None, limit: int, locale: Locale
    ) -> NoticePageModel:
        filters = {"locale": locale.value}
        position = None
        if cursor:
            position = _Cursor(self.settings.session_pepper.get_secret_value()).decode(
                cursor, filters
            )
        params: list[Any] = [principal.user_id, locale.value, locale.value]
        cursor_clause = ""
        if position:
            cursor_clause = " AND (nv.published_at,nv.id) < (%s,%s)"
            params.extend([position.get("publishedAt"), position.get("id")])
        params.append(limit + 1)
        query = f"""
            SELECT n.id::text, nv.id::text AS version_id,
                   coalesce(tt.translated_text,nv.title_en) AS title,
                   coalesce(bt.translated_text,nv.body_en) AS body,
                   nv.published_at,
                   EXISTS (SELECT 1 FROM public.notice_reads nr
                           WHERE nr.user_id=%s AND nr.notice_version_id=nv.id) AS read
            FROM public.notice_versions nv JOIN public.notices n ON n.id=nv.notice_id
            LEFT JOIN public.translation_cache tt ON tt.content_kind='notice'
              AND tt.content_id=nv.id AND tt.content_version=nv.version
              AND tt.locale=%s AND tt.owner_user_id IS NULL
            LEFT JOIN public.translation_cache bt ON bt.content_kind='notice'
              AND bt.content_id=nv.id AND bt.content_version=nv.version
              AND bt.locale=%s AND bt.owner_user_id IS NULL
            WHERE nv.state='published' AND nv.published_at <= now(){cursor_clause}
            ORDER BY nv.published_at DESC,nv.id DESC LIMIT %s
        """
        # Query placeholders: user id, title locale, body locale, cursor/limit.
        params = [principal.user_id, locale.value, locale.value]
        if position:
            params.extend([position.get("publishedAt"), position.get("id")])
        params.append(limit + 1)
        async with self.database.as_user(principal) as connection:
            rows = await (await connection.execute(query, params)).fetchall()
            unread = await (
                await connection.execute(
                    """
                    SELECT count(*) AS unread_count FROM public.notice_versions nv
                    WHERE nv.state='published' AND nv.published_at <= now()
                      AND NOT EXISTS (SELECT 1 FROM public.notice_reads nr
                                      WHERE nr.user_id=public.current_user_id()
                                        AND nr.notice_version_id=nv.id)
                    """
                )
            ).fetchone()
        items = [
            NoticeItemModel.model_validate(
                {
                    "id": row["id"],
                    "versionId": row["version_id"],
                    "title": row["title"],
                    "body": row["body"],
                    "publishedAt": row["published_at"],
                    "read": row["read"],
                }
            )
            for row in rows[:limit]
        ]
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = _Cursor(
                self.settings.session_pepper.get_secret_value()
            ).with_filter_digest(
                {
                    "publishedAt": last["published_at"].isoformat(),
                    "id": last["version_id"],
                },
                filters,
            )
        unread_count = int(unread["unread_count"] if unread else 0)
        return NoticePageModel(
            items=items, unreadCount=unread_count, nextCursor=next_cursor
        )

    async def mark_notice_read(
        self, principal: Principal, notice_version_id: str
    ) -> None:
        async with self.database.as_user(principal) as connection:
            await connection.execute(
                """
                INSERT INTO public.notice_reads(user_id,notice_version_id)
                SELECT public.current_user_id(), id FROM public.notice_versions
                WHERE id=%s AND state='published' AND published_at <= now()
                ON CONFLICT (user_id,notice_version_id) DO NOTHING
                """,
                (notice_version_id,),
            )


__all__ = [
    "CanonicalSchemaModel",
    "DashboardModel",
    "Difficulty",
    "DraftModel",
    "DraftWriteModel",
    "EditorSourcesModel",
    "InputFormat",
    "LearnerRepository",
    "NoticePageModel",
    "PolicyModel",
    "ProblemPageModel",
    "ProblemStatus",
    "ProblemSummaryModel",
    "ProfileModel",
    "ProfilePatchModel",
    "StaticAnalysisModel",
    "SubmissionCreateModel",
    "SubmissionModel",
    "AssessmentResultModel",
]
