use schemasprint_core::{
    CanonicalSchema, DecisionKind, RubricDecision, RubricItem, assess, validate_schema,
};

fn rubric_item(id: &str, weight: u64, critical: bool, implicit: bool) -> RubricItem {
    RubricItem {
        id: id.to_owned(),
        weight,
        critical,
        implicit,
    }
}

fn decision(id: &str, decision: DecisionKind) -> RubricDecision {
    RubricDecision {
        rubric_item_id: id.to_owned(),
        decision,
    }
}

#[test]
fn assessment_uses_exact_integer_authority_and_independent_pass() {
    let rubric = [
        rubric_item("critical", 1, true, false),
        rubric_item("optional", 1_999, false, false),
    ];
    let decisions = [
        decision("critical", DecisionKind::Satisfied),
        decision("optional", DecisionKind::NotMet),
    ];

    let result = assess(&rubric, &decisions, false).expect("valid assessment");
    assert_eq!(result.satisfied_weight, 1);
    assert_eq!(result.total_weight, 2_000);
    assert_eq!(result.numerator, 100);
    assert_eq!(result.denominator, 2_000);
    assert_eq!(result.display_tenths, 1);
    assert!(!result.exact_full);
    assert!(result.passed);
}

#[test]
fn rounded_display_never_grants_exact_full() {
    let rubric = [
        rubric_item("met", 2_499, false, false),
        rubric_item("missed", 1, false, false),
    ];
    let decisions = [
        decision("met", DecisionKind::Satisfied),
        decision("missed", DecisionKind::NotMet),
    ];

    let result = assess(&rubric, &decisions, false).expect("valid assessment");
    assert_eq!(result.display_tenths, 1_000);
    assert!(!result.exact_full);
}

#[test]
fn contradiction_and_critical_decisions_control_pass() {
    let rubric = [rubric_item("required", 1, true, false)];
    let met = [decision("required", DecisionKind::Satisfied)];
    let missed = [decision("required", DecisionKind::NotMet)];

    assert!(!assess(&rubric, &met, true).expect("valid").passed);
    assert!(!assess(&rubric, &missed, false).expect("valid").passed);
}

#[test]
fn rubric_and_decision_invariants_are_rejected() {
    let implicit_critical = [rubric_item("x", 1, true, true)];
    let one_decision = [decision("x", DecisionKind::Satisfied)];
    assert!(
        assess(&implicit_critical, &one_decision, false)
            .expect_err("implicit critical must fail")
            .to_string()
            .starts_with("RUBRIC_IMPLICIT_CRITICAL")
    );

    let rubric = [
        rubric_item("x", 1, false, false),
        rubric_item("y", 1, false, false),
    ];
    let duplicate = [
        decision("x", DecisionKind::Satisfied),
        decision("x", DecisionKind::NotMet),
    ];
    assert!(
        assess(&rubric, &duplicate, false)
            .expect_err("duplicate decisions must fail")
            .to_string()
            .starts_with("DECISION_ID_DUPLICATE")
    );
}

fn valid_schema_json() -> &'static str {
    r#"{
      "schemaVersion": 1,
      "tables": [
        {"id":"parent","name":"parent","columns":[
          {"id":"a","name":"a","dataType":"uuid","nullable":false},
          {"id":"b","name":"b","dataType":"uuid","nullable":false}
        ],"indexes":[],"checks":[],"position":{"x":0,"y":0}},
        {"id":"child","name":"child","columns":[
          {"id":"pa","name":"pa","dataType":"uuid","nullable":false},
          {"id":"pb","name":"pb","dataType":"uuid","nullable":false}
        ],"indexes":[],"checks":[],"position":{"x":1,"y":2}}
      ],
      "relationships": [{
        "id":"fk","fromTableId":"child","fromColumnIds":["pa","pb"],
        "toTableId":"parent","toColumnIds":["a","b"],
        "fromCardinality":"0..*","toCardinality":"1"
      }]
    }"#
}

#[test]
fn schema_validates_relationship_endpoints_and_composite_arity() {
    let schema: CanonicalSchema = serde_json::from_str(valid_schema_json()).expect("valid JSON");
    let result = validate_schema(&schema).expect("valid schema");
    assert_eq!(result.table_count, 2);
    assert_eq!(result.column_count, 4);
    assert_eq!(result.relationship_count, 1);
}

#[test]
fn schema_rejects_invalid_endpoint() {
    let json = valid_schema_json().replace("\"pb\"]", "\"missing\"]");
    let schema: CanonicalSchema = serde_json::from_str(&json).expect("structurally valid JSON");
    assert!(
        validate_schema(&schema)
            .expect_err("unknown endpoint must fail")
            .to_string()
            .starts_with("SCHEMA_RELATIONSHIP_COLUMN_UNKNOWN")
    );
}

#[test]
fn schema_rejects_composite_arity_mismatch() {
    let json = valid_schema_json().replace("[\"a\",\"b\"]", "[\"a\"]");
    let schema: CanonicalSchema = serde_json::from_str(&json).expect("structurally valid JSON");
    assert!(
        validate_schema(&schema)
            .expect_err("arity mismatch must fail")
            .to_string()
            .starts_with("SCHEMA_RELATIONSHIP_ARITY_MISMATCH")
    );
}

#[test]
fn schema_rejects_optional_collection_and_expression_limits() {
    let mut schema: CanonicalSchema =
        serde_json::from_str(valid_schema_json()).expect("valid JSON");
    schema.enums = (0..201)
        .map(|index| {
            let mut object = std::collections::HashMap::new();
            object.insert("name".to_owned(), serde_json::json!(index));
            object
        })
        .collect();
    assert!(
        validate_schema(&schema)
            .expect_err("enum limit must fail")
            .to_string()
            .starts_with("SCHEMA_ENUM_LIMIT_EXCEEDED")
    );

    schema.enums.clear();
    schema.tables[0].columns[0].default_expression = Some("x".repeat(2_001));
    assert!(
        validate_schema(&schema)
            .expect_err("expression limit must fail")
            .to_string()
            .starts_with("SCHEMA_COLUMN_DEFAULT_INVALID")
    );
}

#[test]
fn schema_rejects_oversized_opaque_values() {
    let mut schema: CanonicalSchema =
        serde_json::from_str(valid_schema_json()).expect("valid JSON");
    let mut object = std::collections::HashMap::new();
    object.insert(
        "description".to_owned(),
        serde_json::json!("x".repeat(4_097)),
    );
    schema.tables[0].checks.push(object);
    assert!(
        validate_schema(&schema)
            .expect_err("opaque text limit must fail")
            .to_string()
            .starts_with("SCHEMA_OPAQUE_TEXT_INVALID")
    );
}
