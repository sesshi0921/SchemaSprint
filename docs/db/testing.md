# Local database checks

These checks create a fresh isolated temporary PostgreSQL 16.2 cluster for every test. No production DSN is accepted. The Auth shim emulates claim lookup and database roles only; it does not test Supabase OAuth, JWT validation, MFA or hosted PostgREST configuration.

```sh
uv sync --locked --group local-postgres
uv run ruff check tests
uv run ruff format --check tests
uv run mypy tests
uv run sqlfluff lint db
uv run pytest tests/db -q
```

Python 3.12 is pinned because the development-only `pgserver` distribution supplies that ABI. It starts real PostgreSQL binaries under a temporary directory; session cleanup stops the process. A test superuser sets transaction-local authenticated/anonymous roles and JWT claims; this is not a production authentication mechanism. Function-scoped clusters prevent ordering dependence; each case is destroyed after completion.

For an independently managed disposable database, `docs/db/compose.yaml` supplies loopback-only PostgreSQL with tmpfs storage and a required local password. `docker compose -f docs/db/compose.yaml up -d` requires Docker and `POSTGRES_PASSWORD`; this database is ephemeral and must never store real user data. Compose currently initializes only the test Auth shim; migrations are applied by the test harness, not silently by the container.

The pending review records actual evidence. A green unit suite cannot establish provider integration, production RLS configuration, backup retention or penetration-test completion.
