from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .database import Database
from .security import Principal


class Locale(StrEnum):
    EN = "en"
    JA = "ja"
    ZH_CN = "zh-CN"
    KO = "ko"
    ES = "es"
    PT_BR = "pt-BR"


class RubricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    weight: int = Field(ge=1, le=1_000_000)
    critical: bool
    implicit: bool


class ProblemDetail(BaseModel):
    """Validated DTO matching the explicit root OpenAPI ProblemDetail schema."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(ge=1)
    title: str
    difficulty: Literal["easy", "mid", "hard"]
    genre: str
    inputFormat: Literal["gui", "mermaid", "ddl", "dbml", "mixed"]
    tags: list[str]
    publicationDate: date
    passed: bool
    submitted: bool
    translationStatus: Literal["source", "translated", "pending", "unavailable"]
    problemVersionId: str
    statement: str
    officialAnswer: dict[str, Any]
    explanation: str
    sourceLanguage: Literal["en"] = "en"
    requestedLocale: Locale
    rubricSummary: list[RubricSummary]


@dataclass(slots=True)
class ProblemRepository:
    database: Database

    async def today(
        self, principal: Principal, locale: Locale = Locale.EN
    ) -> ProblemDetail | None:
        query = """
            SELECT p.id::text AS id,
                   pv.id::text AS problem_version_id,
                   pv.version,
                   pv.title,
                   pv.official_solution AS official_answer,
                   pv.difficulty::text AS difficulty,
                   pv.genre,
                   pv.input_format,
                   pv.tags,
                   pc.publication_date,
                   COALESCE(st.translated_text, pv.statement_en) AS statement,
                   COALESCE(et.translated_text, pv.explanation_en) AS explanation,
                   EXISTS (
                       SELECT 1
                       FROM public.submissions AS sub
                       WHERE sub.user_id = public.current_user_id()
                         AND sub.problem_id = p.id
                         AND sub.problem_version_id = pv.id
                   ) AS submitted,
                   EXISTS (
                       SELECT 1
                       FROM public.submissions AS sub
                       JOIN public.submission_results AS sr
                         ON sr.submission_id = sub.id
                       WHERE sub.user_id = public.current_user_id()
                         AND sub.problem_id = p.id
                         AND sub.problem_version_id = pv.id
                         AND sr.passed
                   ) AS passed,
                   COALESCE(
                       jsonb_agg(
                           jsonb_build_object(
                               'id', ri.id::text,
                               'description', ri.description_en,
                               'weight', ri.weight,
                               'critical', ri.is_critical,
                               'implicit', ri.is_implicit
                           ) ORDER BY ri.ordinal
                       ) FILTER (WHERE ri.id IS NOT NULL),
                       '[]'::jsonb
                   ) AS rubric_summary,
                   CASE
                       WHEN %s = 'en' THEN 'source'
                       WHEN st.translated_text IS NOT NULL
                            AND et.translated_text IS NOT NULL THEN 'translated'
                       ELSE 'unavailable'
                   END AS translation_status
            FROM public.publication_calendar AS pc
            JOIN public.problems AS p ON p.id = pc.problem_id
            JOIN public.problem_versions AS pv ON pv.id = pc.problem_version_id
            LEFT JOIN public.rubric_items AS ri
              ON ri.problem_version_id = pv.id
            LEFT JOIN public.translation_cache AS st
              ON st.content_kind = 'problem_statement'
             AND st.content_id = pv.id
             AND st.content_version = pv.version
             AND st.locale = %s
             AND st.owner_user_id IS NULL
            LEFT JOIN public.translation_cache AS et
              ON et.content_kind = 'problem_explanation'
             AND et.content_id = pv.id
             AND et.content_version = pv.version
             AND et.locale = %s
             AND et.owner_user_id IS NULL
            WHERE pc.publication_date = (
                (now() AT TIME ZONE 'Asia/Tokyo') - interval '4 hours'
            )::date
              AND pc.published_at <= now()
            GROUP BY p.id, pv.id, pv.version, pv.title, pv.official_solution,
                     pv.difficulty, pv.genre, pv.input_format, pv.tags,
                     pc.publication_date, st.translated_text, et.translated_text
        """
        locale_value = locale.value
        async with self.database.as_user(principal) as connection:
            row = await (
                await connection.execute(
                    query, (locale_value, locale_value, locale_value)
                )
            ).fetchone()
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
                "tags": list(row["tags"]),
                "publicationDate": row["publication_date"],
                "passed": row["passed"],
                "submitted": row["submitted"],
                "translationStatus": row["translation_status"],
                "problemVersionId": row["problem_version_id"],
                "statement": row["statement"],
                "officialAnswer": row["official_answer"],
                "explanation": row["explanation"],
                "requestedLocale": locale,
                "rubricSummary": row["rubric_summary"],
            }
        )
