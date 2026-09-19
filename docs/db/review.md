# Database gate

Status: NOT PASSED — design draft only.

Completed: conceptual ownership, versioning, exact scoring, authorization boundaries, transaction/idempotency rules, cache-related identity isolation, lifecycle and ER relationships.

Pending: executable PostgreSQL migrations; Compose and test-only Auth shim; independent performance/safety review; live PostgreSQL constraint/RLS/concurrency/erasure tests and query plans. No backend/API implementation may begin until this phase passes. Docker and psql were absent from PATH during initial environment inspection; choose a reproducible local PostgreSQL runtime without modifying production services.

Next action: implement migration/test infrastructure matching decisions.md, then execute the listed database acceptance cases. Jev documentation is not a dependency for these database checks.
