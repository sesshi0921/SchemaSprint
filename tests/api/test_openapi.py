from pathlib import Path
from typing import Any

import yaml
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "openapi.yaml"


def load_spec() -> dict[str, Any]:
    value: object = yaml.safe_load(SPEC_PATH.read_text())
    assert isinstance(value, dict)
    return value


def test_openapi_is_valid() -> None:
    validate(load_spec())


def test_every_route_is_v1_and_operation_ids_are_unique() -> None:
    spec = load_spec()
    paths = spec["paths"]
    assert all(path.startswith("/v1/") for path in paths)
    operation_ids = [
        operation["operationId"]
        for path in paths.values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_cookie_mutations_require_csrf_and_idempotency() -> None:
    spec = load_spec()
    for route, path in spec["paths"].items():
        for method in ("post", "put", "patch", "delete"):
            operation = path.get(method)
            if operation is None:
                continue
            references = {
                parameter.get("$ref")
                for parameter in operation.get("parameters", [])
                if isinstance(parameter, dict)
            }
            assert "#/components/parameters/CsrfToken" in references, (route, method)
            assert "#/components/parameters/IdempotencyKey" in references, (
                route,
                method,
            )


def test_live_payment_and_post_mutation_routes_are_absent() -> None:
    paths = load_spec()["paths"]
    assert not any("checkout" in path or "payment" in path for path in paths)
    community_posts = paths["/v1/problems/{problemId}/posts"]
    assert "patch" not in community_posts and "delete" not in community_posts


def test_schema_payload_bounds_match_reviewed_limits() -> None:
    schemas = load_spec()["components"]["schemas"]
    canonical = schemas["CanonicalSchema"]["properties"]
    assert canonical["tables"]["maxItems"] == 200
    assert canonical["relationships"]["maxItems"] == 2000
    assert schemas["SchemaTable"]["properties"]["columns"]["maxItems"] == 200


def test_session_gates_nullability_and_problem_detail_are_explicit() -> None:
    schemas = load_spec()["components"]["schemas"]
    session = schemas["SessionState"]
    assert "gates" in session["required"]
    gates = session["properties"]["gates"]["anyOf"]
    assert {item.get("type") for item in gates} >= {"object", "null"}

    detail = schemas["ProblemDetail"]
    assert "allOf" not in detail
    assert detail["additionalProperties"] is False
    assert {
        "passed",
        "submitted",
        "problemVersionId",
        "rubricSummary",
        "requestedLocale",
    } <= set(detail["required"])


def test_today_returns_explicit_problem_detail_contract() -> None:
    operation = load_spec()["paths"]["/v1/problems/today"]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/ProblemDetail"}


def test_async_jobs_are_pollable() -> None:
    paths = load_spec()["paths"]
    assert "get" in paths["/v1/jobs/{jobId}"]
    assert "get" in paths["/v1/submissions/{submissionId}"]


def test_admin_surface_covers_required_review_workflows() -> None:
    paths = load_spec()["paths"]
    expected = {
        "/v1/admin/problem-batches",
        "/v1/admin/problems/{problemId}/versions",
        "/v1/admin/problem-versions/{problemVersionId}/validate",
        "/v1/admin/problem-versions/{problemVersionId}/publish",
        "/v1/admin/reports/{reportId}/decision",
        "/v1/admin/posts/{postId}/decision",
        "/v1/admin/approvals",
        "/v1/admin/notices",
        "/v1/admin/notice-versions/{noticeVersionId}/publish",
        "/v1/admin/entitlements",
    }
    assert expected <= paths.keys()
