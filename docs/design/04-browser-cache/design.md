# Browser cache and offline design

Status: approved design for implementation. Applies to the Web PWA; native storage is a later reviewed design.

## Ownership and storage

Use one IndexedDB database, `schemasprint-v1`, with every user-owned/cache record keyed by the internal account ULID. Never use display name, email or provider handle as a namespace. A small unauthenticated preferences record may hold only requested locale/theme and tutorial preference. Cache Storage contains immutable content-hashed application assets only; it does not cache authenticated API responses.

Never persist session cookies, OAuth state/PKCE, JWTs, CSRF tokens, reauthentication proof, provider credentials, raw model traces or admin secrets in IndexedDB, Cache Storage, localStorage or logs. HttpOnly session state remains inaccessible to JavaScript; CSRF is memory-only and reacquired from `/v1/session`. Browser storage is not described as encrypted against XSS or a local device user.

| Store | Key | Value and owner | Retention/invalidation |
|---|---|---|---|
| `accountMeta` | `accountId` | cache schema version, last active time | purge on logout/deletion/account switch |
| `problems` | `[accountId, problemVersionId, locale]` | immutable statement, official answer, explanation, rubric summary, source digest | immutable version; revalidate current pointer daily/online; purge LRU under pressure |
| `problemIndex` | `[accountId, publicationDate]` | current problem/version pointer and list summary | network-first online; max stale 24h; correction replaces pointer, not old version |
| `drafts` | `[accountId, problemId]` | canonical schema, last-valid canonical schema, invalid text buffers, layout, undo checkpoint, update time, optional server revision | never automatic LRU; explicit delete/account purge; local for every member |
| `submissionQueue` | `[accountId, operationId]` | exact problem/version, canonical payload, canonical digest, idempotency UUID, queued time, state, bounded attempt metadata | until confirmed or explicit user discard; never silently evict |
| `submissions` | `[accountId, submissionId]` | immutable submitted snapshot and known result state | purge on account purge; LRU only after safe server confirmation |
| `feedback` | `[accountId, submissionId, feedbackVersion, locale]` | source English, translated content, source digest, model/version metadata | version immutable; purge account; never shared between users |
| `translations` | `[accountId, kind, contentId, contentVersion, locale]` | source English, translated content/status, identifier-preservation flag | invalidate exact source digest/version mismatch; public/member content still account-namespaced |
| `communityPages` | `[accountId, problemVersionId, locale, cursor]` | official-first page, posts, source text and fetched time | stale-while-online-revalidate; short 1h max stale; purge account |
| `notices` | `[accountId, noticeVersionId, locale]` | approved notice version and local read-display state | network reconcile unread state; versions immutable; purge account |
| `outbox` | `[accountId, operationId]` | non-submission idempotent mutation envelope and safe retry state | only allowlisted operation kinds; discard on completion/account purge |

Database-synced drafts remain premium-only. Expiry/revocation disables new server sync but does not destroy the local draft; the UI preserves export and local editing. Server draft conflicts preserve both variants and require an explicit choose/merge action.

## Offline and mutation state machine

A submission queue record is created atomically before the UI reports “queued”. States: `queued → sending → confirmed`, with `attention` for nonretryable version/auth/validation conflicts. A process crash leaves `sending`; a lease timestamp returns it to `queued`. Use one sender per account through Web Locks where available and an IndexedDB lease fallback. Correctness relies on server idempotency, not browser locking.

Reconnect processing reacquires a valid session/CSRF token, then posts the original version and idempotency key. Retry only network failure, 408, 425, 429 and retryable 5xx with server `Retry-After` or bounded exponential backoff/full jitter (1s base, 5m maximum, 8 automatic attempts per foreground cycle). 401/403, version unavailable, payload conflict and validation errors become `attention`; keep the payload and expose retry/export/edit. Never mutate/rebase an answer to a corrected problem version and never generate a new idempotency key for the same logical submission.

Background Sync may wake the sender, but it is an enhancement: `online` events, application start and a manual retry button provide the portable fallback. Closing a tab must not be required for correctness. Queue progress is observable without claiming assessment success; `confirmed` means the server accepted the immutable submission, while assessment is polled separately.

Other offline mutations use the same durable envelope only when their API operation is explicitly safe/idempotent. Account deletion, policy acknowledgement, premium/admin, moderation, reward and publication actions never execute from an unattended offline queue.

## Editor consistency

Every valid edit persists canonical schema plus all source buffers and layout in one IndexedDB transaction. Invalid Mermaid/DDL/DBML updates persist as a separate text buffer with diagnostics but do not replace the last-valid canonical schema/diagram. Arrange writes a new layout and undo checkpoint only after the user presses Arrange. Local write failure/quota exhaustion is blocking and visible; do not display “saved”.

Autosave is debounced, flushes on visibility change when possible and serializes revisions per problem. Multi-tab changes use BroadcastChannel plus revision compare-and-swap; a stale tab creates a recoverable conflict copy rather than overwriting. Browser events such as `beforeunload` are advisory only.

## Service worker and HTTP behavior

- Precache the minimal content-hashed shell and required locale asset for install. Fetch hashed assets cache-first; fetch navigation network-first with a verified shell fallback.
- Do not place authenticated API responses in Cache Storage. The application explicitly copies validated, size-bounded response fields into IndexedDB.
- A new service worker downloads alongside the current one and activates after migrations are ready; never force-reload while dirty drafts or queued submissions exist. Show a user-controlled update action.
- `Clear-Site-Data` is requested on account deletion where supported. Logout/deletion also closes database handles, deletes the account namespace, clears account-bound memory and service-worker messages, then verifies no namespace keys remain. Other offline devices cannot be remotely wiped and this limitation remains disclosed.

## Capacity, eviction and migrations

Soft budget: 50 MiB per account or 70% of reported available quota, whichever is lower. Treat estimates as advisory. Evict in order: expired community pages, old notice translations, old translated problem copies, then server-confirmed submission/result cache. Never automatically evict dirty drafts, queued/outbox operations or their exact problem/version dependencies. If protected data alone exceeds capacity, stop accepting edits before data loss and offer JSON/DDL/DBML export.

IndexedDB schema upgrades are small, deterministic and resumable. Before a destructive representation migration, copy protected records to a temporary versioned store, validate counts/digests, switch metadata, then delete old data. On migration failure keep the old database readable/exportable and disable mutations; never reset the database as recovery. Tests must cover upgrade from every shipped schema version.

## Privacy and failure verification

Required tests: two accounts cannot observe each other's stores; logout/account deletion purges only the intended namespace and memory; offline reload restores invalid text and last-valid diagram; queued submissions survive process restart and retain version/idempotency; duplicate wakeups send one logical operation; auth/version/conflict failures preserve exportable work; correction updates the current pointer without rewriting queued/history; quota failures never claim save; server draft conflicts preserve both copies; service-worker upgrade cannot discard dirty state.
