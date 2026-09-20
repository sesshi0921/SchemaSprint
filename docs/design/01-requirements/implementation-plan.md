# MVP implementation plan and release boundary

Status: executable plan; the requirements in the neighboring design documents remain authoritative.

## Delivery order

1. **Data and policy:** PostgreSQL migration, RLS, lifecycle constraints, audit rows, and negative tests.
2. **API boundary:** OpenAPI validation, Worker ingress limits, Python authorization/session policy, ULID and idempotency rules.
3. **Assessment:** static canonical-schema analysis first, then Jev decision input; persist immutable snapshots and never execute learner SQL.
4. **Web client:** React/Vite/PWA shell, locale/theme, problem/archive/workspace/result/dashboard/settings/notices, then the shared ER editor and ELK arrange action.
5. **Operations:** OAuth provider configuration, content-generation/feedback workers, translation, notifications, cost controls, and protected deployment.
6. **Release verification:** CI, authenticated browser E2E, accessibility, mobile viewport, RLS/integration negatives, backup/restore, and owner acceptance.

## MVP boundary

Included: the complete agreed Web/PWA learner journey, published daily/archive problems, five editor input modes, static plus Jev assessment, independent pass state, feedback entitlement boundary, community posts restricted to exact-full results, notices/reports, OAuth allowlist, server drafts for an enabled entitlement, and sandbox-only premium/ads flags.

Not enabled in MVP: live billing, production rewarded ads, native app-store release, arbitrary SQL execution, automatic new-account provisioning, high-cost grading fallback, and any provider integration whose data-processing, credentials, or contract has not passed its release gate.

## Acceptance gates

- **Local gate:** database/API/Rust/frontend checks pass and all checked-in unit/integration tests are green.
- **Browser gate:** the CI Playwright suite passes on desktop and mobile, including axe-core on the sign-in surface; an allowlisted owner account completes open → edit → submit → result → feedback without data loss.
- **Security gate:** real Supabase JWT/RLS/OAuth/MFA/CSRF negatives, secret/dependency/SAST scan, deletion/restore drill, and independent penetration review pass.
- **Operations gate:** Cloudflare Pages/Worker/Container smoke, provider timeouts and retries, backup/rollback, monitoring/alerts, cost budget, legal/consent review, and owner approval pass.

No gate may be represented as passed by a stub or a pending asynchronous job. Unmet external gates remain visible in the release review documents and README.
