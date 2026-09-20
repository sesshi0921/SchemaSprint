#![forbid(unsafe_code)]

use std::collections::{HashMap, HashSet};
use std::fmt::{Display, Formatter};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyString};
use pythonize::{depythonize, pythonize};
use serde::{Deserialize, Serialize};

const MAX_RUBRIC_ITEMS: usize = 2_000;
const MAX_WEIGHT: u64 = 1_000_000;
const MAX_TABLES: usize = 200;
const MAX_COLUMNS_PER_TABLE: usize = 200;
const MAX_RELATIONSHIPS: usize = 2_000;
const MAX_RELATIONSHIP_COLUMNS: usize = 32;
const MAX_ENUMS: usize = 200;
const MAX_VIEWS: usize = 200;
const MAX_TRIGGERS: usize = 200;
const MAX_POLICIES: usize = 500;
const MAX_PARTITIONS: usize = 200;
const MAX_TABLE_OBJECTS: usize = 200;
const MAX_OPAQUE_KEYS: usize = 200;
const MAX_OPAQUE_ARRAY_ITEMS: usize = 2_000;
const MAX_OPAQUE_DEPTH: usize = 32;
const MAX_OPAQUE_STRING_CHARS: usize = 4_096;
const MAX_SCHEMA_TEXT_CHARS: usize = 2_000;
const MAX_PY_PAYLOAD_BYTES: usize = 1024 * 1024;
const MAX_PY_TEXT_BYTES: usize = 1024 * 1024;
const MAX_PY_DEPTH: usize = 64;
const MAX_PY_COLLECTION_ITEMS: usize = 2_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationError {
    code: &'static str,
    detail: Option<String>,
}

impl ValidationError {
    const fn new(code: &'static str) -> Self {
        Self { code, detail: None }
    }

    fn with_detail(code: &'static str, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: Some(detail.into()),
        }
    }
}

impl Display for ValidationError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        match &self.detail {
            Some(detail) => write!(formatter, "{}: {detail}", self.code),
            None => formatter.write_str(self.code),
        }
    }
}

impl std::error::Error for ValidationError {}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RubricItem {
    pub id: String,
    pub weight: u64,
    pub critical: bool,
    pub implicit: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DecisionKind {
    Satisfied,
    NotMet,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RubricDecision {
    pub rubric_item_id: String,
    pub decision: DecisionKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Assessment {
    pub satisfied_weight: u64,
    pub total_weight: u64,
    /// Exact score is `numerator / denominator`; no float is authoritative.
    pub numerator: u64,
    pub denominator: u64,
    /// Display score in tenths of one point (0..=1000).
    pub display_tenths: u16,
    pub exact_full: bool,
    pub passed: bool,
}

/// Computes exact weighted scoring and the independent pass verdict.
///
/// # Errors
///
/// Returns a stable [`ValidationError`] when the rubric or decisions violate
/// boundedness, uniqueness, coverage, weight, or implicit-critical invariants.
pub fn assess(
    rubric: &[RubricItem],
    decisions: &[RubricDecision],
    contradiction: bool,
) -> Result<Assessment, ValidationError> {
    if rubric.is_empty() {
        return Err(ValidationError::new("RUBRIC_EMPTY"));
    }
    if rubric.len() > MAX_RUBRIC_ITEMS {
        return Err(ValidationError::new("RUBRIC_TOO_LARGE"));
    }

    let mut rubric_by_id = HashMap::with_capacity(rubric.len());
    let mut total_weight = 0_u64;
    for item in rubric {
        if item.id.is_empty() {
            return Err(ValidationError::new("RUBRIC_ID_EMPTY"));
        }
        if item.weight == 0 || item.weight > MAX_WEIGHT {
            return Err(ValidationError::with_detail(
                "RUBRIC_WEIGHT_INVALID",
                &item.id,
            ));
        }
        if item.implicit && item.critical {
            return Err(ValidationError::with_detail(
                "RUBRIC_IMPLICIT_CRITICAL",
                &item.id,
            ));
        }
        if rubric_by_id.insert(item.id.as_str(), item).is_some() {
            return Err(ValidationError::with_detail(
                "RUBRIC_ID_DUPLICATE",
                &item.id,
            ));
        }
        total_weight = total_weight
            .checked_add(item.weight)
            .ok_or_else(|| ValidationError::new("SCORE_ARITHMETIC_OVERFLOW"))?;
    }

    if decisions.len() != rubric.len() {
        return Err(ValidationError::new("DECISION_COVERAGE_INCOMPLETE"));
    }
    let mut seen = HashSet::with_capacity(decisions.len());
    let mut satisfied_weight = 0_u64;
    let mut all_critical_satisfied = true;
    for decision in decisions {
        if !seen.insert(decision.rubric_item_id.as_str()) {
            return Err(ValidationError::with_detail(
                "DECISION_ID_DUPLICATE",
                &decision.rubric_item_id,
            ));
        }
        let item = rubric_by_id
            .get(decision.rubric_item_id.as_str())
            .ok_or_else(|| {
                ValidationError::with_detail("DECISION_ID_UNKNOWN", &decision.rubric_item_id)
            })?;
        if decision.decision == DecisionKind::Satisfied {
            satisfied_weight = satisfied_weight
                .checked_add(item.weight)
                .ok_or_else(|| ValidationError::new("SCORE_ARITHMETIC_OVERFLOW"))?;
        } else if item.critical {
            all_critical_satisfied = false;
        }
    }

    let numerator = satisfied_weight
        .checked_mul(100)
        .ok_or_else(|| ValidationError::new("SCORE_ARITHMETIC_OVERFLOW"))?;
    let scaled = satisfied_weight
        .checked_mul(1_000)
        .and_then(|value| value.checked_add(total_weight / 2))
        .ok_or_else(|| ValidationError::new("SCORE_ARITHMETIC_OVERFLOW"))?;
    let display_tenths = u16::try_from(scaled / total_weight)
        .map_err(|_| ValidationError::new("SCORE_ARITHMETIC_OVERFLOW"))?;

    Ok(Assessment {
        satisfied_weight,
        total_weight,
        numerator,
        denominator: total_weight,
        display_tenths,
        exact_full: satisfied_weight == total_weight,
        passed: all_critical_satisfied && !contradiction,
    })
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CanonicalSchema {
    pub schema_version: u32,
    pub tables: Vec<SchemaTable>,
    pub relationships: Vec<SchemaRelationship>,
    #[serde(default)]
    pub enums: Vec<OpaqueObject>,
    #[serde(default)]
    pub views: Vec<OpaqueObject>,
    #[serde(default)]
    pub triggers: Vec<OpaqueObject>,
    #[serde(default)]
    pub policies: Vec<OpaqueObject>,
    #[serde(default)]
    pub partitions: Vec<OpaqueObject>,
}

pub type OpaqueObject = HashMap<String, serde_json::Value>;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SchemaTable {
    pub id: String,
    pub name: String,
    pub columns: Vec<SchemaColumn>,
    pub indexes: Vec<OpaqueObject>,
    pub checks: Vec<OpaqueObject>,
    pub position: Position,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SchemaColumn {
    pub id: String,
    pub name: String,
    pub data_type: String,
    pub nullable: bool,
    #[serde(default)]
    pub primary_key: bool,
    #[serde(default)]
    pub default_expression: Option<String>,
    #[serde(default)]
    pub generated_expression: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Position {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SchemaRelationship {
    pub id: String,
    pub from_table_id: String,
    pub from_column_ids: Vec<String>,
    pub to_table_id: String,
    pub to_column_ids: Vec<String>,
    pub from_cardinality: Cardinality,
    pub to_cardinality: Cardinality,
    #[serde(default)]
    pub on_delete: Option<OnDelete>,
}

#[derive(Debug, Clone, Deserialize)]
pub enum Cardinality {
    #[serde(rename = "0..1")]
    ZeroOrOne,
    #[serde(rename = "1")]
    One,
    #[serde(rename = "0..*")]
    ZeroOrMany,
    #[serde(rename = "1..*")]
    OneOrMany,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OnDelete {
    NoAction,
    Restrict,
    Cascade,
    SetNull,
    SetDefault,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchemaSummary {
    pub valid: bool,
    pub table_count: usize,
    pub column_count: usize,
    pub relationship_count: usize,
}

/// Validates bounded canonical-schema structure and relationship references.
///
/// # Errors
///
/// Returns a stable [`ValidationError`] when limits, identifiers, endpoint
/// references, or composite relationship arity are invalid.
#[allow(clippy::too_many_lines)]
pub fn validate_schema(schema: &CanonicalSchema) -> Result<SchemaSummary, ValidationError> {
    if schema.schema_version != 1 {
        return Err(ValidationError::new("SCHEMA_VERSION_UNSUPPORTED"));
    }
    if schema.tables.len() > MAX_TABLES {
        return Err(ValidationError::new("SCHEMA_TABLE_LIMIT_EXCEEDED"));
    }
    if schema.relationships.len() > MAX_RELATIONSHIPS {
        return Err(ValidationError::new("SCHEMA_RELATIONSHIP_LIMIT_EXCEEDED"));
    }
    if schema.enums.len() > MAX_ENUMS {
        return Err(ValidationError::new("SCHEMA_ENUM_LIMIT_EXCEEDED"));
    }
    if schema.views.len() > MAX_VIEWS {
        return Err(ValidationError::new("SCHEMA_VIEW_LIMIT_EXCEEDED"));
    }
    if schema.triggers.len() > MAX_TRIGGERS {
        return Err(ValidationError::new("SCHEMA_TRIGGER_LIMIT_EXCEEDED"));
    }
    if schema.policies.len() > MAX_POLICIES {
        return Err(ValidationError::new("SCHEMA_POLICY_LIMIT_EXCEEDED"));
    }
    if schema.partitions.len() > MAX_PARTITIONS {
        return Err(ValidationError::new("SCHEMA_PARTITION_LIMIT_EXCEEDED"));
    }

    let mut table_columns: HashMap<&str, HashSet<&str>> =
        HashMap::with_capacity(schema.tables.len());
    let mut column_count = 0_usize;
    let mut opaque_nodes = 0_usize;
    for table in &schema.tables {
        validate_identifier(&table.id, "SCHEMA_TABLE_ID_INVALID")?;
        validate_bounded_text(&table.name, 128, "SCHEMA_TABLE_NAME_INVALID")?;
        if table.columns.len() > MAX_COLUMNS_PER_TABLE {
            return Err(ValidationError::with_detail(
                "SCHEMA_COLUMN_LIMIT_EXCEEDED",
                &table.id,
            ));
        }
        if table.indexes.len() > MAX_TABLE_OBJECTS {
            return Err(ValidationError::with_detail(
                "SCHEMA_INDEX_LIMIT_EXCEEDED",
                &table.id,
            ));
        }
        if table.checks.len() > MAX_TABLE_OBJECTS {
            return Err(ValidationError::with_detail(
                "SCHEMA_CHECK_LIMIT_EXCEEDED",
                &table.id,
            ));
        }
        for object in table.indexes.iter().chain(table.checks.iter()) {
            validate_opaque_object(object, &mut opaque_nodes)?;
        }
        let mut columns = HashSet::with_capacity(table.columns.len());
        for column in &table.columns {
            validate_identifier(&column.id, "SCHEMA_COLUMN_ID_INVALID")?;
            validate_bounded_text(&column.name, 128, "SCHEMA_COLUMN_NAME_INVALID")?;
            validate_bounded_text(&column.data_type, 256, "SCHEMA_COLUMN_TYPE_INVALID")?;
            if let Some(default_expression) = &column.default_expression {
                validate_bounded_text(
                    default_expression,
                    MAX_SCHEMA_TEXT_CHARS,
                    "SCHEMA_COLUMN_DEFAULT_INVALID",
                )?;
            }
            if let Some(generated_expression) = &column.generated_expression {
                validate_bounded_text(
                    generated_expression,
                    MAX_SCHEMA_TEXT_CHARS,
                    "SCHEMA_COLUMN_GENERATED_INVALID",
                )?;
            }
            if !columns.insert(column.id.as_str()) {
                return Err(ValidationError::with_detail(
                    "SCHEMA_COLUMN_ID_DUPLICATE",
                    format!("{}:{}", table.id, column.id),
                ));
            }
        }
        column_count = column_count
            .checked_add(table.columns.len())
            .ok_or_else(|| ValidationError::new("SCHEMA_SIZE_OVERFLOW"))?;
        if table_columns.insert(table.id.as_str(), columns).is_some() {
            return Err(ValidationError::with_detail(
                "SCHEMA_TABLE_ID_DUPLICATE",
                &table.id,
            ));
        }
        if !table.position.x.is_finite() || !table.position.y.is_finite() {
            return Err(ValidationError::with_detail(
                "SCHEMA_POSITION_INVALID",
                &table.id,
            ));
        }
    }

    for object in schema
        .enums
        .iter()
        .chain(schema.views.iter())
        .chain(schema.triggers.iter())
        .chain(schema.policies.iter())
        .chain(schema.partitions.iter())
    {
        validate_opaque_object(object, &mut opaque_nodes)?;
    }

    let mut relationship_ids = HashSet::with_capacity(schema.relationships.len());
    for relationship in &schema.relationships {
        validate_identifier(&relationship.id, "SCHEMA_RELATIONSHIP_ID_INVALID")?;
        validate_identifier(
            &relationship.from_table_id,
            "SCHEMA_RELATIONSHIP_TABLE_ID_INVALID",
        )?;
        validate_identifier(
            &relationship.to_table_id,
            "SCHEMA_RELATIONSHIP_TABLE_ID_INVALID",
        )?;
        if !relationship_ids.insert(relationship.id.as_str()) {
            return Err(ValidationError::with_detail(
                "SCHEMA_RELATIONSHIP_ID_DUPLICATE",
                &relationship.id,
            ));
        }
        validate_endpoint(
            &table_columns,
            &relationship.from_table_id,
            &relationship.from_column_ids,
            &relationship.id,
        )?;
        validate_endpoint(
            &table_columns,
            &relationship.to_table_id,
            &relationship.to_column_ids,
            &relationship.id,
        )?;
        if relationship.from_column_ids.len() != relationship.to_column_ids.len() {
            return Err(ValidationError::with_detail(
                "SCHEMA_RELATIONSHIP_ARITY_MISMATCH",
                &relationship.id,
            ));
        }
    }

    Ok(SchemaSummary {
        valid: true,
        table_count: schema.tables.len(),
        column_count,
        relationship_count: schema.relationships.len(),
    })
}

fn validate_identifier(value: &str, code: &'static str) -> Result<(), ValidationError> {
    validate_bounded_text(value, 128, code)
}

fn validate_bounded_text(
    value: &str,
    max_chars: usize,
    code: &'static str,
) -> Result<(), ValidationError> {
    if value.is_empty() || value.chars().count() > max_chars {
        return Err(ValidationError::new(code));
    }
    Ok(())
}

fn validate_opaque_object(object: &OpaqueObject, nodes: &mut usize) -> Result<(), ValidationError> {
    if object.len() > MAX_OPAQUE_KEYS {
        return Err(ValidationError::new("SCHEMA_OPAQUE_KEY_LIMIT_EXCEEDED"));
    }
    for (key, value) in object {
        validate_bounded_text(key, 128, "SCHEMA_OPAQUE_KEY_INVALID")?;
        validate_opaque_value(value, 0, nodes)?;
    }
    Ok(())
}

fn validate_opaque_value(
    value: &serde_json::Value,
    depth: usize,
    nodes: &mut usize,
) -> Result<(), ValidationError> {
    *nodes = (*nodes)
        .checked_add(1)
        .ok_or_else(|| ValidationError::new("SCHEMA_OPAQUE_SIZE_OVERFLOW"))?;
    if depth > MAX_OPAQUE_DEPTH || *nodes > MAX_PY_PAYLOAD_BYTES {
        return Err(ValidationError::new("SCHEMA_OPAQUE_DEPTH_EXCEEDED"));
    }
    match value {
        serde_json::Value::String(text) => {
            validate_bounded_text(text, MAX_OPAQUE_STRING_CHARS, "SCHEMA_OPAQUE_TEXT_INVALID")
        }
        serde_json::Value::Array(values) => {
            if values.len() > MAX_OPAQUE_ARRAY_ITEMS {
                return Err(ValidationError::new("SCHEMA_OPAQUE_ARRAY_LIMIT_EXCEEDED"));
            }
            for item in values {
                validate_opaque_value(item, depth + 1, nodes)?;
            }
            Ok(())
        }
        serde_json::Value::Object(values) => {
            if values.len() > MAX_OPAQUE_KEYS {
                return Err(ValidationError::new("SCHEMA_OPAQUE_KEY_LIMIT_EXCEEDED"));
            }
            for (key, item) in values {
                validate_bounded_text(key, 128, "SCHEMA_OPAQUE_KEY_INVALID")?;
                validate_opaque_value(item, depth + 1, nodes)?;
            }
            Ok(())
        }
        serde_json::Value::Null | serde_json::Value::Bool(_) | serde_json::Value::Number(_) => {
            Ok(())
        }
    }
}

fn validate_endpoint<'a>(
    table_columns: &HashMap<&'a str, HashSet<&'a str>>,
    table_id: &str,
    column_ids: &[String],
    relationship_id: &str,
) -> Result<(), ValidationError> {
    let columns = table_columns.get(table_id).ok_or_else(|| {
        ValidationError::with_detail("SCHEMA_RELATIONSHIP_TABLE_UNKNOWN", relationship_id)
    })?;
    if column_ids.is_empty() || column_ids.len() > MAX_RELATIONSHIP_COLUMNS {
        return Err(ValidationError::with_detail(
            "SCHEMA_RELATIONSHIP_ARITY_INVALID",
            relationship_id,
        ));
    }
    let mut seen = HashSet::with_capacity(column_ids.len());
    for column_id in column_ids {
        if !seen.insert(column_id.as_str()) {
            return Err(ValidationError::with_detail(
                "SCHEMA_RELATIONSHIP_COLUMN_DUPLICATE",
                relationship_id,
            ));
        }
        if !columns.contains(column_id.as_str()) {
            return Err(ValidationError::with_detail(
                "SCHEMA_RELATIONSHIP_COLUMN_UNKNOWN",
                relationship_id,
            ));
        }
    }
    Ok(())
}

fn reject_py_payload(code: &'static str) -> PyErr {
    PyValueError::new_err(code)
}

fn consume_py_budget(budget: &mut usize, amount: usize) -> PyResult<()> {
    *budget = (*budget)
        .checked_sub(amount)
        .ok_or_else(|| reject_py_payload("PAYLOAD_SIZE_LIMIT_EXCEEDED"))?;
    Ok(())
}

fn preflight_py_value(value: &Bound<'_, PyAny>, depth: usize, budget: &mut usize) -> PyResult<()> {
    if depth > MAX_PY_DEPTH {
        return Err(reject_py_payload("PAYLOAD_RECURSION_LIMIT_EXCEEDED"));
    }
    consume_py_budget(budget, 1)?;

    if value.is_none()
        || value.is_instance_of::<pyo3::types::PyBool>()
        || value.is_instance_of::<pyo3::types::PyInt>()
        || value.is_instance_of::<pyo3::types::PyFloat>()
    {
        return Ok(());
    }
    if value.is_instance_of::<PyString>() {
        let text = value
            .downcast::<PyString>()
            .map_err(|_| reject_py_payload("PAYLOAD_TYPE_INVALID"))?
            .to_str()
            .map_err(|_| reject_py_payload("PAYLOAD_TEXT_INVALID"))?;
        if text.len() > MAX_PY_TEXT_BYTES {
            return Err(reject_py_payload("PAYLOAD_TEXT_LIMIT_EXCEEDED"));
        }
        consume_py_budget(budget, text.len())?;
        return Ok(());
    }
    if let Ok(dict) = value.downcast::<PyDict>() {
        if dict.len() > MAX_PY_COLLECTION_ITEMS {
            return Err(reject_py_payload("PAYLOAD_COLLECTION_LIMIT_EXCEEDED"));
        }
        for (key, item) in dict.iter() {
            preflight_py_value(&key, depth + 1, budget)?;
            preflight_py_value(&item, depth + 1, budget)?;
        }
        return Ok(());
    }
    if value.is_instance_of::<pyo3::types::PyList>()
        || value.is_instance_of::<pyo3::types::PyTuple>()
    {
        let length = value
            .len()
            .map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?;
        if length > MAX_PY_COLLECTION_ITEMS {
            return Err(reject_py_payload("PAYLOAD_COLLECTION_LIMIT_EXCEEDED"));
        }
        for item in value
            .try_iter()
            .map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?
        {
            let item = item.map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?;
            preflight_py_value(&item, depth + 1, budget)?;
        }
        return Ok(());
    }
    Err(reject_py_payload("PAYLOAD_TYPE_INVALID"))
}

fn preflight_collection(
    parent: &Bound<'_, PyDict>,
    key: &str,
    limit: usize,
    error: &'static str,
) -> PyResult<()> {
    let Some(value) = parent
        .get_item(key)
        .map_err(|_| reject_py_payload("PAYLOAD_OBJECT_INVALID"))?
    else {
        return Ok(());
    };
    let length = value
        .len()
        .map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?;
    if length > limit {
        return Err(reject_py_payload(error));
    }
    Ok(())
}

fn preflight_schema_shape(schema: &Bound<'_, PyAny>) -> PyResult<()> {
    let root = schema
        .downcast::<PyDict>()
        .map_err(|_| reject_py_payload("SCHEMA_PAYLOAD_INVALID"))?;
    preflight_collection(root, "tables", MAX_TABLES, "SCHEMA_TABLE_LIMIT_EXCEEDED")?;
    preflight_collection(
        root,
        "relationships",
        MAX_RELATIONSHIPS,
        "SCHEMA_RELATIONSHIP_LIMIT_EXCEEDED",
    )?;
    preflight_collection(root, "enums", MAX_ENUMS, "SCHEMA_ENUM_LIMIT_EXCEEDED")?;
    preflight_collection(root, "views", MAX_VIEWS, "SCHEMA_VIEW_LIMIT_EXCEEDED")?;
    preflight_collection(
        root,
        "triggers",
        MAX_TRIGGERS,
        "SCHEMA_TRIGGER_LIMIT_EXCEEDED",
    )?;
    preflight_collection(
        root,
        "policies",
        MAX_POLICIES,
        "SCHEMA_POLICY_LIMIT_EXCEEDED",
    )?;
    preflight_collection(
        root,
        "partitions",
        MAX_PARTITIONS,
        "SCHEMA_PARTITION_LIMIT_EXCEEDED",
    )?;

    if let Some(tables) = root
        .get_item("tables")
        .map_err(|_| reject_py_payload("PAYLOAD_OBJECT_INVALID"))?
    {
        for table in tables
            .try_iter()
            .map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?
        {
            let table = table.map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?;
            if let Ok(table) = table.downcast::<PyDict>() {
                preflight_collection(
                    table,
                    "columns",
                    MAX_COLUMNS_PER_TABLE,
                    "SCHEMA_COLUMN_LIMIT_EXCEEDED",
                )?;
                preflight_collection(
                    table,
                    "indexes",
                    MAX_TABLE_OBJECTS,
                    "SCHEMA_INDEX_LIMIT_EXCEEDED",
                )?;
                preflight_collection(
                    table,
                    "checks",
                    MAX_TABLE_OBJECTS,
                    "SCHEMA_CHECK_LIMIT_EXCEEDED",
                )?;
            }
        }
    }
    if let Some(relationships) = root
        .get_item("relationships")
        .map_err(|_| reject_py_payload("PAYLOAD_OBJECT_INVALID"))?
    {
        for relationship in relationships
            .try_iter()
            .map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?
        {
            let relationship =
                relationship.map_err(|_| reject_py_payload("PAYLOAD_COLLECTION_INVALID"))?;
            if let Ok(relationship) = relationship.downcast::<PyDict>() {
                preflight_collection(
                    relationship,
                    "fromColumnIds",
                    MAX_RELATIONSHIP_COLUMNS,
                    "SCHEMA_RELATIONSHIP_ARITY_INVALID",
                )?;
                preflight_collection(
                    relationship,
                    "toColumnIds",
                    MAX_RELATIONSHIP_COLUMNS,
                    "SCHEMA_RELATIONSHIP_ARITY_INVALID",
                )?;
            }
        }
    }
    Ok(())
}

#[pyfunction]
fn compute_assessment(
    py: Python<'_>,
    rubric: &Bound<'_, PyAny>,
    decisions: &Bound<'_, PyAny>,
    contradiction: bool,
) -> PyResult<Py<PyAny>> {
    let mut budget = MAX_PY_PAYLOAD_BYTES;
    preflight_py_value(rubric, 0, &mut budget)?;
    preflight_py_value(decisions, 0, &mut budget)?;
    let rubric: Vec<RubricItem> =
        depythonize(rubric).map_err(|_| PyValueError::new_err("RUBRIC_PAYLOAD_INVALID"))?;
    let decisions: Vec<RubricDecision> =
        depythonize(decisions).map_err(|_| PyValueError::new_err("DECISION_PAYLOAD_INVALID"))?;
    let assessment = assess(&rubric, &decisions, contradiction)
        .map_err(|error| PyValueError::new_err(error.to_string()))?;
    pythonize(py, &assessment)
        .map(Bound::unbind)
        .map_err(|_| PyValueError::new_err("ASSESSMENT_SERIALIZATION_FAILED"))
}

#[pyfunction]
fn validate_canonical_schema(py: Python<'_>, schema: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    preflight_schema_shape(schema)?;
    let mut budget = MAX_PY_PAYLOAD_BYTES;
    preflight_py_value(schema, 0, &mut budget)?;
    let schema: CanonicalSchema =
        depythonize(schema).map_err(|_| PyValueError::new_err("SCHEMA_PAYLOAD_INVALID"))?;
    let summary =
        validate_schema(&schema).map_err(|error| PyValueError::new_err(error.to_string()))?;
    pythonize(py, &summary)
        .map(Bound::unbind)
        .map_err(|_| PyValueError::new_err("SCHEMA_SERIALIZATION_FAILED"))
}

#[pymodule]
fn schemasprint_core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(compute_assessment, module)?)?;
    module.add_function(wrap_pyfunction!(validate_canonical_schema, module)?)?;
    Ok(())
}
