# PostgreSQL design

Status: design in progress; migration and database-executed authorization tests required before phase PASS.

## Identity and trust

Supabase `auth.users.id` UUID maps uniquely to application `users.id` ULID (26 uppercase Crockford Base32 characters, first character 0–7). Validate IDs, but authorization never depends on ULID unpredictability. Provider identity uniqueness is `(issuer, subject)`; a verified email can bootstrap only an approved unbound entry, then permanent subject binding prevents reassignment by changed email. Linking is explicit ownership proof, never email equality. Display names are deliberately nonunique.

PostgREST ordinary requests propagate the verified user access JWT; `auth.uid()` resolves membership. Enable and force RLS on exposed tables, revoke anonymous access, grant authenticated users only the necessary columns/actions. Identity, premium, grades, role, publication, moderation and approval writes never belong to authenticated clients. Application authorization AND RLS must both pass. Server/owner credentials are confined to explicitly privileged code paths, with current actor and action checks and MFA for administration. RLS bypass service credentials are not the ordinary query path.

Use a separate `private` schema for sessions, provider tokens, jobs, idempotency, reward/billing events, admin audits and deletion ledger. No PostgREST exposure/grants on that schema. Application RPCs have pinned search paths, explicit grants, schema-qualified objects and no caller-controlled SQL. Privileged functions validate current database identity and policy rather than accepting trusted user IDs from request payloads.

## Entity groups and ownership

| Group | Tables / key constraints | Lifecycle and access |
|---|---|---|
| Accounts | users; provider_identities; allowlist; age_declarations; policy_versions; policy_acknowledgements; role_grants | ULID↔UUID unique; subjects unique; owner-only role/allowlist writes; self profile read/update excludes immutable authority columns |
| Sessions | private.sessions; private.oauth_attempts | Random opaque cookie hash, encrypted refresh material, expiry/revoked timestamps; one-use state/PKCE; never expose token material |
| Membership | entitlements; private.billing_events | Server/admin source, validity range, unique provider event ID; audit reason; membership derived at current time, not sticky client premium boolean |
| Content | problems; problem_versions; rubric_items; publication_calendar; private.publication_events | Stable problem ID, version unique per problem, exact normalized-content hash, one calendar date per problem/day; dates in JST; read published versions only |
| Drafts | workspaces | Unique user/problem; canonical JSON + layout + source buffers; revision integer for compare-and-swap; premium write authorization evaluated at transaction time |
| Assessment | submissions; submission_results; requirement_results | User-owned immutable schema/context snapshot; exact version FK; unique user/idempotency key and payload hash; one result per submission; one decision per rubric item |
| Feedback | feedback_versions; private.feedback_requests; private.ad_reward_attempts | User/submission ownership composite FK; first successful feedback per user/problem; one reward consumed by one request; new version on regeneration |
| Translation | translation_cache | Unique immutable content kind/ID/version/locale and owner partition; private feedback never shared; original English stays authoritative |
| Community | posts; moderation_decisions; reports | Submission owner must match author; exact full-score required; premoderation default held; published members-only; no author edit/delete privileges |
| Notices | notices; notice_versions; notice_reads; admin_approvals | Versioned draft/approved/published state; separate correction/notice approval references; read key user/version; approvals never inferred from model output |
| Operations | private.jobs; private.outbox; private.admin_audit; private.deletion_ledger; private.restore_runs | Leased work, bounded attempts, delivery deduplication; actor/reason/time audit without raw secrets/content; minimal erasure tombstones |

## Content and immutable assessment

`problem_versions` holds the English statement, official canonical solution, explanation, difficulty/genre/format/tags, normalized content hash, quality evidence, created timestamp, and publication eligibility state. `rubric_items` stores stable item ID, positive bounded integer weight, critical flag, implicit flag, textual derivation, importance, and evaluation specification. CHECK rejects critical+implicit and missing derivation on implicit items; naming/extensibility are excluded from scoring specifications. Freeze content and rubric before any publication/submission reference.

Prevent changing a frozen version or its rubric by trigger; corrections insert a new version and advance the public pointer only after owner approval. Keep old published versions accessible for queued submissions and historical view. A report never hides a problem. Publication uses one atomic transaction with a unique daily key and outbox event; retries cannot send multiple logical notices or assign another problem to a day.

Submission snapshots contain canonical schema, format metadata, problem/rubric snapshot, engine/model identifiers, and version. Separate pending work from finalized evidence: submissions immutable from creation, results inserted only at successful finalization, with append-only requirement decisions in that same transaction. Missing/failed provider results are pending/failed jobs, never a stored false score. Reject extra, duplicate or missing rubric-item decisions.

Use bounded positive integer weights (1–1,000,000 each; max 2,000 items). Store integer satisfied_weight and total_weight, CHECK `0 <= satisfied_weight <= total_weight`, and derive score from the ratio. `exact_full` is equality, never rounded numeric value. Compute pass using all critical decisions and contradiction flag, not score threshold. Finalization validates sums and criticals from frozen rubric rows in a database function/trigger; client or provider aggregate scores are never authority.

Post creation locks/reads the result and verifies owner, equality of exact weights, finalized state and moderation. Posts copy no editable grading authority; retain submission/version FK. No nullable author permits abandoned personal content after deletion.

## Transaction and query paths

- Versioned immutable content reads: index `(published_at, id)`; search title/tags with PostgreSQL text search GIN; publication date/difficulty/genre/format indexes verified with EXPLAIN against seeded workload.
- Dashboard: aggregate distinct passed problem IDs for current owner, then join publication date and stored difficulty; weekday uses JST publication date, not attempt timestamp. Index submissions `(user_id, problem_id, created_at DESC)` and results by submission ID.
- Submission idempotency: unique `(user_id, idempotency_key)` plus canonical request digest. Same key/different body is conflict, same body returns original resource. Preserve keys while the submission exists; account erasure removes them.
- Draft CAS: `UPDATE ... WHERE revision = expected_revision RETURNING ...`; stale mutation is conflict, never last-write-wins data loss.
- Feedback: lock user/problem quota row, reserve first-free/reward entitlement once, call provider outside transaction, then finalize atomically. Failure releases reservation; retry reuses operation ID. A lease/reconciliation path repairs process death. Rereads never consume entitlement. Unique provider/attempt/request references reject duplicate callbacks.
- Jobs/outbox: `(state, available_at)` partial indexes, `FOR UPDATE SKIP LOCKED`, lease expiry, bounded retries. No lock held across network I/O; at-least-once delivery requires consumer idempotency. Successful daily publication emits owner-email event too.
- Admin approvals: reference exact target version digest and action; editing the draft invalidates applicability. Correction and notice approval are independent. Audit append occurs in same transaction as action.

## Deletion and retention

Account deletion revokes sessions first, removes live user-owned records/posts, provider identities and Auth user, clears local storage best effort, and records minimal tombstone before acknowledging completion. Cascade dependent private rows; preserve unrelated published problems. Avoid cascading deleted admin identities into public content or audit history: administrative actor references may be null, with non-personal opaque audit subject retained only per approved policy. Failure of Auth deletion remains visible and retryable, never claims completed erasure prematurely.

Backups expire at most 30 days. Keep minimal keyed Auth-subject tombstones long enough to cover all restorable backups; deny tombstoned identities during restoration, reapply deletion before opening traffic, then verify. Provider deletion and regional backup commitments remain release gates. No arbitrary raw answer/JWT/email in audit/outbox logs. Translation rows tied to deleted feedback/posts cascade. Revocation of premium stops new server-draft writes but allows self export/read until deletion or an explicitly approved retention policy; no silent erasure on expiry.

## Migration and local verification

Local Compose uses vanilla PostgreSQL with a test-only Supabase `auth.uid()` claims shim and minimal auth schema/roles. Production migration assumes real Supabase Auth; never deploy the shim there. SQL migrations are checked in, additive first, transactional where supported, with lock/statement timeouts. Apply from empty database and replay in CI; owner backups before production migration, no automatic destructive downgrade. Record rollback/roll-forward per migration.

Required database evidence before phase PASS: schema apply/reapply behavior; constraints; anonymous/other-user read/write denial; premium draft negative; forbidden grade/role/publish writes; immutable update rejection; complete result arithmetic/pass check; idempotency concurrency; exact-score post gate; correction preserving old data; immediate cascade erasure; publication boundary/query plans. Database tests must execute PostgreSQL, not rely solely on regex, SQLite or mocked repository methods.
