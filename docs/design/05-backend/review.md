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
- Jev modes without an implemented adapter resolve durably as `failed` with
  `JEV_UNAVAILABLE`; the development stub is deterministic and local-only.
- RLS tests cover owner isolation, future publication/notice visibility,
  private feedback translation isolation, immutable assessment records, and
  premium-expiry draft behavior. Static checks: Ruff and mypy pass for the
  learner implementation and focused tests.

## Required operations still unimplemented

The root OpenAPI contract has 43 operations. This phase does **not** claim
implementation of the following groups:

- OAuth start/callback/logout, onboarding age/policy acknowledgement, account
  export/deletion and re-authentication proof.
- Feedback generation/read, reward attempts, translation reads/jobs, generic
  job polling, community posts/reports, and all moderator/admin content,
  validation, publication, moderation, approval, and entitlement routes.
- A production Jev adapter, provider timeout/retry worker, and asynchronous
  assessment job lifecycle.

These are missing implementation, not simulated success. The phase therefore
cannot pass the backend gate or be released as an MVP. The authorized database
policy must allow owners to read/export existing drafts after premium expiry,
while INSERT/UPDATE/DELETE remain premium-gated; this distinction must be
verified by the DB suite.
