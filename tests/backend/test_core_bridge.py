from typing import cast

import pytest
import schemasprint_core  # type: ignore[import-untyped]
from schemasprint_api.core import (
    CanonicalSchemaPayload,
    CoreValidationError,
    compute_assessment,
    validate_canonical_schema,
)


def valid_schema() -> CanonicalSchemaPayload:
    return cast(
        CanonicalSchemaPayload,
        {
            "schemaVersion": 1,
            "tables": [
                {
                    "id": "parent",
                    "name": "parent",
                    "columns": [
                        {
                            "id": "id",
                            "name": "id",
                            "dataType": "uuid",
                            "nullable": False,
                        }
                    ],
                    "indexes": [],
                    "checks": [],
                    "position": {"x": 0.0, "y": 0.0},
                },
                {
                    "id": "child",
                    "name": "child",
                    "columns": [
                        {
                            "id": "parent_id",
                            "name": "parent_id",
                            "dataType": "uuid",
                            "nullable": False,
                        }
                    ],
                    "indexes": [],
                    "checks": [],
                    "position": {"x": 1.0, "y": 2.0},
                },
            ],
            "relationships": [
                {
                    "id": "child_parent",
                    "fromTableId": "child",
                    "fromColumnIds": ["parent_id"],
                    "toTableId": "parent",
                    "toColumnIds": ["id"],
                    "fromCardinality": "0..*",
                    "toCardinality": "1",
                }
            ],
        },
    )


def test_extension_wheel_exports_are_importable() -> None:
    assert callable(schemasprint_core.compute_assessment)
    assert callable(schemasprint_core.validate_canonical_schema)


def test_assessment_bridge_preserves_exact_arithmetic_and_pass_state() -> None:
    result = compute_assessment(
        [
            {"id": "critical", "weight": 1, "critical": True, "implicit": False},
            {"id": "optional", "weight": 1_999, "critical": False, "implicit": False},
        ],
        [
            {"rubricItemId": "critical", "decision": "satisfied"},
            {"rubricItemId": "optional", "decision": "not_met"},
        ],
        False,
    )
    assert result.numerator == 100
    assert result.denominator == 2_000
    assert result.display_tenths == 1
    assert result.exact_full is False
    assert result.passed is True


def test_schema_bridge_returns_typed_summary() -> None:
    summary = validate_canonical_schema(valid_schema())
    assert summary.valid is True
    assert summary.table_count == 2
    assert summary.column_count == 2
    assert summary.relationship_count == 1


def test_rust_domain_error_is_exposed_as_stable_code() -> None:
    with pytest.raises(
        CoreValidationError, match="SCHEMA_RELATIONSHIP_COLUMN_UNKNOWN"
    ) as exc:
        schema = valid_schema()
        relationships = schema["relationships"]
        assert isinstance(relationships, list)
        relationship = relationships[0]
        assert isinstance(relationship, dict)
        relationship["toColumnIds"] = ["missing"]
        validate_canonical_schema(schema)
    assert exc.value.code == "SCHEMA_RELATIONSHIP_COLUMN_UNKNOWN"


def test_boundary_rejects_extra_rubric_fields_before_extension() -> None:
    with pytest.raises(CoreValidationError, match="RUBRIC_PAYLOAD_INVALID"):
        compute_assessment(
            [
                {
                    "id": "x",
                    "weight": 1,
                    "critical": False,
                    "implicit": False,
                    "extra": "rejected",
                }
            ],
            [{"rubricItemId": "x", "decision": "satisfied"}],
            False,
        )


def test_boundary_rejects_oversized_rubric_before_conversion() -> None:
    item = {"id": "x", "weight": 1, "critical": False, "implicit": False}
    with pytest.raises(CoreValidationError, match="RUBRIC_TOO_LARGE"):
        compute_assessment([item] * 2_001, [], False)


def test_ffi_rejects_text_payload_over_one_mib() -> None:
    oversized = {
        "id": "x" * (1024 * 1024 + 1),
        "weight": 1,
        "critical": False,
        "implicit": False,
    }
    with pytest.raises(CoreValidationError, match="PAYLOAD_TEXT_LIMIT_EXCEEDED"):
        compute_assessment([oversized], [], False)
