# Database gate review

Date: 2026-09-20. Status: **PASS for database-design and foundational migration scope**. This does not approve production deployment.

## Reviewed

- PostgreSQL ownership, normalization, cardinality, versioning, lifecycle, indexes, retention and authorization boundaries.
- `db/migrations/0001_initial.sql`, local Auth shim, isolated PostgreSQL harness, Compose alternative and CI checks.
- RLS/default-denial, security-definer search paths, identity/age/latest-policy/allowlist gates, private schema isolation and authority-write denial.
- Frozen content/rubrics, publication eligibility and exact 04:00 JST boundary, version-matched submissions, complete weighted results, independent pass state, exact-full posts and canonical snapshot integrity.
- Premium drafts/revisions, feedback/reward ownership, idempotency uniqueness/locking, account deletion cascades and index-usable dashboard query.

## Evidence

Commands executed from the repository root:

```sh
uv sync --locked --group local-postgres
uv run ruff check tests
uv run ruff format --check tests
uv run mypy tests
uv run sqlfluff lint db
uv run pytest tests/db -q
```

Result: Ruff, formatting, mypy and SQLFluff passed; **31 tests passed in 30.19s**. Each test receives a fresh temporary PostgreSQL 16.2 cluster, not SQLite or a repository mock. Concurrency cases verify that rubric mutation blocks concurrent freeze and duplicate submission idempotency keys serialize then reject. A reordered isolation probe also passed.

Independent performance/safety review found and caused repair of: unsafe security-definer path acceptance; frozen rubric movement/races; publication update bypass; nullable Jev confidence; policy-version supersession; graded/post schema mismatch; feedback problem/reward ownership; unfrozen submissions; empty frozen versions; test ordering dependence. Final independent review: PASS.

## Residual downstream/release gates

- Validate real Supabase Auth roles, JWT/PostgREST behavior, default grants and RLS migrations in staging; the local shim proves PostgreSQL policy mechanics only.
- API/service transactions must enforce request-digest idempotency semantics, draft compare-and-swap, approvals/MFA, deletion orchestration and provider lifecycle. Database constraints are defense-in-depth, not the whole authorization layer.
- Run representative-volume `EXPLAIN (ANALYZE, BUFFERS)` and latency/load tests after API query shapes and traffic assumptions are fixed. The current forced-index test proves index usability, not production latency.
- Verify hosted backup deletion/reapplication, region/retention, vendor terms and restore evidence before release.
- Compose is an optional PostgreSQL 17.6 disposable environment; CI evidence uses the pinned PostgreSQL 16.2 development wheel. Staging must target the actual supported Supabase major/minor before migration approval.

Gate decision: database phase may advance to the root OpenAPI contract. These residuals remain explicit API/infrastructure/release gates and must not be reported as complete.
