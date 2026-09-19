# Implementation baseline

Status: requirements reviewed; implementation and verification pending. Source: all six domain documents linked from `../README.md`. This baseline resolves implementation defaults, not a replacement or reduction of their Must scope.

## Product and release boundary

Learners practice interpreting requirements into database schemas, compare alternative valid designs, and receive per-requirement assessment. Primary journey: approved OAuth identity → age/policy acknowledgement → daily or archived problem → edit → immutable submission → result → optional feedback/post → dashboard.

All agreed features remain Must. Native apps, live payments, production advertising, expensive grading fallback, comments, and other unagreed additions are Won't for this delivery. Monthly/annual billing lifecycle remains sandbox-testable; owner-managed premium remains real application functionality. Release readiness is distinct from a runnable local implementation. Missing provider credentials, independent penetration testing, legal approval, and authorized infrastructure deployment cannot be represented as completed tests.

Leading validation signal: an eligible learner completes the core journey without lost edits or unauthorized disclosure. Before beta release, run an owner acceptance session on desktop and mobile; each acceptance ID below must have evidence, not a percentage-of-features claim.

## Resolved defaults and contradictions

| Topic | Implementation decision |
|---|---|
| Source precedence | Explicit goal decisions override older defaults; agreed domain requirements remain authoritative. Record future changes explicitly. |
| Color | Gray/light-gray surfaces, Kikyō accent `#5654A2`, light/dark semantic tokens; no gradients. Functional error/success colors remain separate. |
| Score/pass | Positive integer rubric weights, exact numerator/denominator, display-only decimal rounding. Critical completeness plus no contradiction determines pass independently. |
| Jev uncertainty | Obtain official provider/API documentation before claiming integration. Typed local test adapter is visibly development-only; missing real provider yields unavailable/pending, never fabricated success. |
| Static versus semantic | Static parser facts are not semantic correctness. Structural isomorphism/naming differences cannot become automatic failure. Remaining semantic requirements go to Jev. |
| Ads disabled | First user/problem feedback is free; subsequent nonpremium requests return honest ad-unavailable status in deployed MVP. Sandbox verified rewards are test-only. No browser callback can grant production entitlement. |
| Billing disabled | No checkout CTA or live payment calls. Admin grants/revocations require current authorization, MFA and audit. Sandbox event replay covers monthly/annual lifecycle. |
| Drafts | All users: per-account local IndexedDB. Premium: server drafts with revision conflict detection. Explicit export remains available. |
| History versus deletion | Immutable history prohibits ordinary updates, not required account erasure. Delete private submissions and linked posts in the deletion workflow; preserve minimal non-content deletion evidence. |
| Offline versions | Queue explicit published version and idempotency key. Corrections do not rebase queued answers. Deleted/unavailable versions or revoked access fail visibly without discarding local work. |
| Undo and advanced controls | Undo/redo includes Arrange; searchable tables; optional advanced metadata panel. No unsupported silent round-trip loss. |
| Moderation | Initial single owner handles held posts/reports. Model decisions are evidence, not authority to grant privileges or auto-approve corrections. |
| Names and identity | Generated neutral name; duplicate display names permitted. ULID maps one-to-one to Auth UUID. No implicit account linking by email. |
| Runtime | React/Vite client, same-origin Worker gateway, Supabase identity/Postgres. Python orchestration and native Rust extension run in a private, idle-sleep Cloudflare Container behind the gateway; see `runtime-decision.md`. Paid deployment awaits owner budget approval. No GPU. |

## Ordered delivery and gates

1. Requirements: this baseline, complete traceability, contradictions, independent review.
2. Database: ERD, reproducible PostgreSQL, migrations, constraints, ownership/RLS, lifecycle and negative tests; reviewed before API work.
3. API: root OpenAPI contract for every journey, errors, bounds, auth, pagination and idempotency; reviewed before handlers.
4. Browser cache: per-account storage, versions, TTL/eviction, queue reconciliation and logout/deletion; reviewed before client storage code.
5. Backend: Python orchestration, Rust domain logic, auth/policy, transaction-safe grading/entitlements, jobs and provider adapters; independent performance/safety review.
6. Frontend: shared semantic theme/components, complete workspace and editor, all six locale assets, mobile and offline/PWA; browser verification and independent review.
7. Delivery: CI checks, Terraform, sandbox flags, restore/rollback drills, cost alerts, legal drafts and accurate README; no live deployment without authorization.

Do not treat later-phase planning as implementation. Each gate records checks and unresolved release conditions. Use small commits, never include credentials or unrelated user files.

## Acceptance evidence matrix

Each range means every individual criterion, not a representative sample. Evidence must identify test names/commands and actual results in its phase review.

| Source criteria | Required verification |
|---|---|
| AC-PROD-001; ARC-04–06; SEC-01–02 | Google/GitHub identity/allowlist, age and policy gates; changed email and cross-user/RLS denial; MFA and CSRF/session negatives |
| AC-PROD-002,004,006; AC-LEARN-001–003; ARC-12 | 04:00 JST boundary, leap/month rollover, independent RNG, bounded retries/exact duplicates, archived queries, all filters, unique pass calendar |
| AC-PROD-003; ARC-13–14 | Offline editing/reload, reconnect idempotency, version pinning, account switch/logout isolation, expired auth and quota failures |
| AC-PROD-005; AC-LEARN-004–008; ARC-07–11 | Exact weighted arithmetic, critical/noncritical/implicit constraints, alternative designs, no naming score, immutable snapshots, confidence labeling, provider errors |
| AC-PROD-007 | Six locale selection and assets; NMT cache versions; preserved identifiers and private feedback isolation |
| AC-PROD-008; OPS-04,06–07 | Feedback failure/retry/reread, reward replay/no-fill, premium expiry/refund/admin audit; no live billing |
| AC-PROD-009; ARC-15 | Separate correction/notice approvals, held content, old-version labels, unread/archive behavior |
| AC-EXP-001–006 | GUI/forms/text synchronization, all listed PostgreSQL metadata, invalid text preservation, lossy export warnings, Crow's Foot, explicit ELK and undo, mobile/keyboard/tutorial |
| AC-EXP-007–009 | Exact-full-score post authorization (including 99.96 rejection), safe links, no author edit/delete/comments, client diagram rendering, held premoderation |
| ARC-01–03 | Web/PWA production build; versioned native-ready API; no Next.js or required always-on GPU |
| SEC-03–05 | Security scans, independent pentest release gate, deletion/restore/reapplied ledger, reviewed policies/consent and nonessential tracking disabled |
| OPS-01–03,05,08–10 | Vendor/cost evidence, tested alerts/breaker, infrastructure validation, backup/rollback drills, outage behavior and operational runbooks |

## Bounds and test workloads

Initial reversible safety limits: schema payload 1 MiB, 200 tables, 200 columns/table, 2,000 relations, 2,000 rubric items; 10,000-character explanation. Reject oversize input before parser/provider work. Local draft capacity failures must be visible. Benchmark static parse/validation and layout against small (5 tables), medium (50), and maximum accepted schemas; document actual hardware/results, not invented latency claims. Keep UI parsing/layout off the interactive path when measurement requires a worker. Pagination max 100; provider concurrency/retries/timeouts must be explicit and fail closed.

## Open release conditions (not permission to shrink scope)

- Jev official identity, API contract, credentials and calibrated quality/confidence thresholds.
- Owner-approved monthly infrastructure budget, region and vendor data-processing terms; do not enable paid resources meanwhile.
- Real OAuth callback/provider settings, approved identities and owner MFA bootstrap.
- External NMT/LLM/email credentials and delivery verification.
- Legal review of actual policy drafts; independent penetration test; real backup retention and restoration evidence.
- Secure production rewarded-ad feasibility remains deferred with production ads explicitly disabled by the goal.

## Obligations beyond numbered acceptance IDs

Verify profile display-name editing separately from provider identity; problem/answer/grading/translation/other report categories; owner content/rubric editing and held-report tooling; community original-language toggle; naming and extensibility feedback without score effects; policy-update acknowledgement blocking learning while logout/deletion/legal rights remain reachable; infrastructure-origin email for successful daily publication as well as failures and near-limit cost. These source obligations are Must even where an acceptance ID groups them implicitly.
