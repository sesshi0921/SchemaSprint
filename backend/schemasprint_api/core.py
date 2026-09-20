"""Typed boundary for the deterministic Rust assessment engine.

The extension is the authority for canonical schema validation and exact score
arithmetic. This module only validates the Python-facing shape, translates
Rust's stable errors, and validates the returned objects before they cross the
backend boundary.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, NotRequired, Protocol, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

try:
    import schemasprint_core as _extension  # type: ignore[import-untyped]
except ModuleNotFoundError as error:  # pragma: no cover - packaging failure
    raise RuntimeError(
        "schemasprint-core is required; install the locked Rust extension wheel"
    ) from error


class RubricItemPayload(TypedDict):
    """The exact JSON-compatible rubric item accepted by the Rust extension."""

    id: str
    weight: int
    critical: bool
    implicit: bool


class RubricDecisionPayload(TypedDict):
    """The exact JSON-compatible rubric decision accepted by the extension."""

    rubricItemId: str
    decision: Literal["satisfied", "not_met"]


class SchemaColumnPayload(TypedDict):
    id: str
    name: str
    dataType: str
    nullable: bool
    primaryKey: NotRequired[bool]
    defaultExpression: NotRequired[str | None]
    generatedExpression: NotRequired[str | None]


class SchemaPositionPayload(TypedDict):
    x: float
    y: float


class SchemaTablePayload(TypedDict):
    id: str
    name: str
    columns: Sequence[SchemaColumnPayload]
    indexes: Sequence[Mapping[str, object]]
    checks: Sequence[Mapping[str, object]]
    position: SchemaPositionPayload


class SchemaRelationshipPayload(TypedDict):
    id: str
    fromTableId: str
    fromColumnIds: Sequence[str]
    toTableId: str
    toColumnIds: Sequence[str]
    fromCardinality: Literal["0..1", "1", "0..*", "1..*"]
    toCardinality: Literal["0..1", "1", "0..*", "1..*"]
    onDelete: NotRequired[
        Literal["no_action", "restrict", "cascade", "set_null", "set_default"] | None
    ]


class CanonicalSchemaPayload(TypedDict):
    """Canonical schema payload shared by all editor representations."""

    schemaVersion: int
    tables: Sequence[SchemaTablePayload]
    relationships: Sequence[SchemaRelationshipPayload]
    enums: NotRequired[Sequence[Mapping[str, object]]]
    views: NotRequired[Sequence[Mapping[str, object]]]
    triggers: NotRequired[Sequence[Mapping[str, object]]]
    policies: NotRequired[Sequence[Mapping[str, object]]]
    partitions: NotRequired[Sequence[Mapping[str, object]]]


class _Extension(Protocol):
    def compute_assessment(
        self, rubric: object, decisions: object, contradiction: bool
    ) -> object: ...

    def validate_canonical_schema(self, schema: object) -> object: ...


_RUST = cast(_Extension, _extension)
_MAX_RUBRIC_ITEMS = 2_000


class CoreValidationError(ValueError):
    """Stable, safe-to-return validation failure from the Rust boundary."""

    def __init__(self, message: str) -> None:
        self.code, _, detail = message.partition(": ")
        self.detail = detail or None
        super().__init__(message)


class _AssessmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    satisfied_weight: StrictInt = Field(alias="satisfiedWeight")
    total_weight: StrictInt = Field(alias="totalWeight")
    numerator: StrictInt
    denominator: StrictInt
    display_tenths: StrictInt = Field(alias="displayTenths")
    exact_full: StrictBool = Field(alias="exactFull")
    passed: StrictBool


class _SchemaSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    valid: StrictBool
    table_count: StrictInt = Field(alias="tableCount")
    column_count: StrictInt = Field(alias="columnCount")
    relationship_count: StrictInt = Field(alias="relationshipCount")


@dataclass(frozen=True, slots=True)
class Assessment:
    """Exact weighted assessment; ``numerator / denominator`` is authoritative."""

    satisfied_weight: int
    total_weight: int
    numerator: int
    denominator: int
    display_tenths: int
    exact_full: bool
    passed: bool


@dataclass(frozen=True, slots=True)
class SchemaSummary:
    valid: bool
    table_count: int
    column_count: int
    relationship_count: int


def _rust_error(error: ValueError) -> CoreValidationError:
    return CoreValidationError(str(error))


def _parse_rubric_item(item: Mapping[str, object]) -> RubricItemPayload:
    if not isinstance(item, Mapping):
        raise CoreValidationError("RUBRIC_PAYLOAD_INVALID")
    payload = {
        "id": item.get("id"),
        "weight": item.get("weight"),
        "critical": item.get("critical"),
        "implicit": item.get("implicit"),
    }
    if not isinstance(payload["id"], str) or not isinstance(payload["weight"], int):
        raise CoreValidationError("RUBRIC_PAYLOAD_INVALID")
    if not isinstance(payload["critical"], bool) or not isinstance(
        payload["implicit"], bool
    ):
        raise CoreValidationError("RUBRIC_PAYLOAD_INVALID")
    if set(item) != {"id", "weight", "critical", "implicit"}:
        raise CoreValidationError("RUBRIC_PAYLOAD_INVALID")
    return cast(RubricItemPayload, payload)


def _parse_decision(item: Mapping[str, object]) -> RubricDecisionPayload:
    if not isinstance(item, Mapping):
        raise CoreValidationError("DECISION_PAYLOAD_INVALID")
    if set(item) != {"rubricItemId", "decision"}:
        raise CoreValidationError("DECISION_PAYLOAD_INVALID")
    rubric_item_id = item.get("rubricItemId")
    decision = item.get("decision")
    if not isinstance(rubric_item_id, str) or decision not in {"satisfied", "not_met"}:
        raise CoreValidationError("DECISION_PAYLOAD_INVALID")
    return {
        "rubricItemId": rubric_item_id,
        "decision": cast(Literal["satisfied", "not_met"], decision),
    }


def compute_assessment(
    rubric: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    contradiction: bool,
) -> Assessment:
    """Compute exact weighted score and independent pass state in Rust."""

    if not isinstance(contradiction, bool):
        raise CoreValidationError("ASSESSMENT_PAYLOAD_INVALID")
    if len(rubric) > _MAX_RUBRIC_ITEMS:
        raise CoreValidationError("RUBRIC_TOO_LARGE")
    if len(decisions) > _MAX_RUBRIC_ITEMS:
        raise CoreValidationError("DECISION_PAYLOAD_TOO_LARGE")
    try:
        normalized_rubric = [_parse_rubric_item(item) for item in rubric]
        normalized_decisions = [_parse_decision(item) for item in decisions]
        result = _RUST.compute_assessment(
            normalized_rubric, normalized_decisions, contradiction
        )
        parsed = _AssessmentModel.model_validate(result)
    except ValueError as error:
        raise _rust_error(error) from error
    return Assessment(
        satisfied_weight=parsed.satisfied_weight,
        total_weight=parsed.total_weight,
        numerator=parsed.numerator,
        denominator=parsed.denominator,
        display_tenths=parsed.display_tenths,
        exact_full=parsed.exact_full,
        passed=parsed.passed,
    )


def validate_canonical_schema(schema: CanonicalSchemaPayload) -> SchemaSummary:
    """Validate canonical schema bounds and relationship references in Rust."""

    if not isinstance(schema, Mapping):
        raise CoreValidationError("SCHEMA_PAYLOAD_INVALID")
    try:
        result = _RUST.validate_canonical_schema(dict(schema))
        parsed = _SchemaSummaryModel.model_validate(result)
    except ValueError as error:
        raise _rust_error(error) from error
    return SchemaSummary(
        valid=parsed.valid,
        table_count=parsed.table_count,
        column_count=parsed.column_count,
        relationship_count=parsed.relationship_count,
    )


__all__ = [
    "Assessment",
    "CanonicalSchemaPayload",
    "CoreValidationError",
    "RubricDecisionPayload",
    "RubricItemPayload",
    "SchemaSummary",
    "compute_assessment",
    "validate_canonical_schema",
]
