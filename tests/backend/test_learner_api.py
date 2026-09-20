from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import AnyHttpUrl, SecretStr, ValidationError
from schemasprint_api.config import Environment, Settings
from schemasprint_api.learner import (
    CanonicalSchemaModel,
    LearnerRepository,
    ProfilePatchModel,
    SubmissionCreateModel,
    _Cursor,  # noqa: PLC2701
)


def settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_dsn=SecretStr("postgresql://unused"),
        session_pepper=SecretStr("p" * 32),
        csrf_key=SecretStr("c" * 32),
        allowed_origin=AnyHttpUrl("https://schemasprint.test"),
    )


def test_cursor_is_signed_and_filter_bound() -> None:
    cursor = _Cursor("p" * 32)
    filters = {"locale": "en", "status": None}
    token = cursor.with_filter_digest({"date": "2026-09-20", "id": "problem"}, filters)
    assert cursor.decode(token, filters)["id"] == "problem"
    with pytest.raises(HTTPException):
        cursor.decode(token, {"locale": "ja", "status": None})


def test_canonical_schema_is_checked_by_rust_boundary() -> None:
    valid: dict[str, Any] = {
        "schemaVersion": 1,
        "tables": [],
        "relationships": [],
    }
    assert CanonicalSchemaModel.model_validate(valid).schemaVersion == 1
    with pytest.raises(ValidationError):
        CanonicalSchemaModel.model_validate(
            {"schemaVersion": 1, "tables": [], "relationships": [{"id": "bad"}]}
        )


def test_static_stub_only_satisfies_explicit_objective_specs() -> None:
    schema = {
        "schemaVersion": 1,
        "tables": [
            {
                "id": "users",
                "name": "users",
                "columns": [],
                "indexes": [],
                "checks": [],
                "position": {"x": 0, "y": 0},
            }
        ],
        "relationships": [],
    }
    rubric = [
        {"id": "r1", "evaluator_spec": {"requiredTable": "users"}},
        {"id": "r2", "evaluator_spec": {"requiredTable": "orders"}},
        {"id": "r3", "evaluator_spec": {"kind": "semantic"}},
    ]
    decisions = LearnerRepository._static_decisions(schema, rubric)
    assert [item["decision"] for item in decisions] == [
        "satisfied",
        "not_met",
        "not_met",
    ]


def test_profile_patch_rejects_empty_patch() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchModel.model_validate({})


def test_submission_route_ids_are_ulids() -> None:
    with pytest.raises(ValidationError):
        SubmissionCreateModel.model_validate(
            {
                "problemId": "not-an-ulid",
                "problemVersionId": "01ARZ3NDEKTSV4RRFFQ69G5FAY",
                "canonicalSchema": {
                    "schemaVersion": 1,
                    "tables": [],
                    "relationships": [],
                },
                "editorSources": {},
                "staticAnalysis": {"parserVersion": "client", "diagnostics": []},
            }
        )
