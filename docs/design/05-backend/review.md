# Backend implementation gate review

Date: 2026-09-20  
Status: **NOT PASSED**

## Implemented and verified in this phase

- FastAPI BFF wiring for health/session, published problem list/detail/today,
  premium draft read/write/delete, submissions/results, dashboard, notices,
  policies, and profile read/update.
- Cookie principal and learning-gate checks, CSRF and UUID idempotency headers,
  signed filter-bound cursors, optimistic draft `If-Match`, request limits,
  rate limiting, structured errors, and security headers.
- Submission idempotency is bound to `(user_id, idempotency_key)` in the
  database. The immutable row stores the exact editor/problem/rubric and
  server static-analysis snapshots. Rust-provided numerator, denominator,
  display score, and exact-full result are persisted and replayed; Python does
  not recompute the score on reads.
- Jev modes without a configured endpoint resolve durably as `failed` with
  `JEV_UNAVAILABLE`; the development stub is deterministic and local-only.
  The external Jev adapter now validates the typed System One response and
  retries only bounded transient failures without sending identity or tokens.
- OAuth/provider-unavailable behavior, onboarding, profile/export/deletion,
  feedback/translation/community/report/job reads, and owner/admin content,
  publication, moderation, approvals, entitlements, and batch-job routes are
  implemented with CSRF, idempotency, MFA/re-authentication, role checks and
  audit writes where required.
- RLS tests cover owner isolation, future publication/notice visibility,
  private feedback translation isolation, immutable assessment records, and
  premium-expiry draft behavior. Static checks: Ruff and mypy pass for the
  learner implementation and focused tests.

## Remaining release gates

- Groq is now a server-only, bounded adapter with explicit unavailable,
  timeout, rate-limit, and upstream errors; it is not enabled by default.
  Feedback generation still requires an authorized provider payload boundary,
  strict generated-output persistence, NMT, and a durable worker lifecycle.
  Provider timeout/retry workers and the full asynchronous assessment/feedback
  execution lifecycle remain unconnected.
- Real Supabase OAuth/JWT/RLS/MFA integration, authenticated browser E2E,
  provider contract tests, and production backup/restore evidence remain
  release gates.

These are explicit provider/integration gates, not simulated success. The
authorized database policy allows owners to read/export existing drafts after
premium expiry, while INSERT/UPDATE/DELETE remain premium-gated; this is
covered by the DB suite.
