# API decisions

The root `openapi.yaml` is the contract. The Cloudflare Worker is the sole public ingress. It terminates same-origin requests, applies request/body/rate bounds and forwards to the private Python service. Python revalidates the session, current gate state, ownership and action; PostgreSQL RLS is a second boundary.

## Security and semantics

- Web authentication uses a `Secure`, `HttpOnly`, `SameSite=Lax`, `__Host-` session cookie. OAuth state and PKCE are one-use and server-held. Callback redirects are allowlisted paths, never arbitrary origins.
- Every cookie-authenticated mutation requires `X-CSRF-Token`. Every mutation also requires an UUID idempotency key; the server binds it to user, operation and canonical payload digest. Same key/same body returns the original outcome; same key/different body returns 409.
- OAuth callback is protected by one-use state instead of a CSRF header. Reads never cause entitlement, moderation, publication or model side effects.
- Error bodies use safe problem details and request IDs. No database, authorization rule, prompt, model trace, provider body, email, token or secret appears in a client error.
- Pagination cursors are opaque, signed/versioned, limited to 100 rows, and bound to normalized filters. Dates are ISO 8601; daily attribution is a JST date.
- `202` means durable work was accepted, not succeeded. Clients poll the returned resource/job with bounded backoff. Provider unavailability remains pending/failed and never becomes fabricated feedback or assessment.

## Resource rules

- Problem responses expose only published/current or explicitly historical versions. The official answer is intentionally present before submission and causes no mutation.
- Submissions carry explicit problem/version and the full canonical schema; server static parsing is authoritative. Client diagnostics are evidence for UX only and are never trusted as grade facts.
- Numeric score is deterministic from stored per-item decisions. API returns one decimal for display plus `exactFull`; posting checks exact stored weights, not the decimal.
- Draft `If-Match` contains the last revision. Premium and current policy/access gates are checked in the same transaction as compare-and-swap.
- Feedback is tied to the selected owned submission. Existing versions are free reads. Production reward creation honestly returns disabled/no-fill in MVP; sandbox success is unavailable in production configuration.
- Community creation accepts no schema body: the server copies the graded submission snapshot. Posts have no edit/delete routes. Links are rendered client-side only after HTTPS validation and are never fetched by this service.
- Admin mutations require owner/admin action authorization, MFA/recent-auth proof, reason, exact target digest and same-transaction audit. Correction and notice approvals are independent.
- Live billing and checkout endpoints are deliberately absent. Admin premium is supported; sandbox billing replay belongs to private test/operations tooling, not a public payment API.

## Bounds

Worker and Python reject bodies above 1 MiB before parsing. Canonical schema maxima mirror the database-design baseline (200 tables, 200 columns/table, 2,000 relations and rubric decisions). Text and cursor limits are explicit in the contract. Provider calls have implementation-level deadlines/retry budgets and no request holds a database transaction across network I/O.

## Compatibility

Only `/v1` is supported. Additive optional fields are allowed; removing/renaming fields or changing semantics requires a new version. Future Expo clients use bearer/native-secure token endpoints that must be added as a new reviewed security scheme; they do not copy Web cookies.
