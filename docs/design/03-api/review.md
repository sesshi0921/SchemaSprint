# API gate review

Date: 2026-09-20. Status: **PARTIAL — contract and local handlers verified; provider/integration gates remain**.

## Scope and checks

Reviewed the root `openapi.yaml` against every agreed product, assessment, editor/community, architecture, security and operations journey. The contract contains 43 versioned operations covering OAuth/session/onboarding/policies, profile/export/deletion, daily/archive/search, premium drafts, immutable submissions/results/feedback, explicit translations, dashboard, exact-full posts, reports, notices, jobs and owner administration for generation/content versions/validation/publication/moderation/approvals/entitlements.

Checks performed:

- OpenAPI 3.1 structural/reference validation and unique operation IDs.
- Default cookie authentication; state/PKCE callback exception; CSRF and UUID idempotency headers on every mutation.
- Explicit body/list/schema limits, opaque cursor pagination, optimistic draft revision and safe structured errors.
- Async work is pollable; 202 never claims success. Submission and feedback failures cannot fabricate results.
- Score/pass/exact-full semantics, selected-submission feedback and no schema supplied by a community poster.
- Separate correction/notice approvals, exact target digest, recent-auth header and audited reason on privileged changes.
- Version-aware NMT route and private feedback ownership; English originals are included for fallback/toggle.
- No checkout/live-payment route, no community post edit/delete/comment route and production ads remain explicitly disabled.

Automated evidence:

```sh
uv run python -m openapi_spec_validator openapi.yaml
uv run ruff check tests
uv run ruff format --check tests
uv run mypy tests
uv run pytest tests/api -q
```

Results: specification `OK`; static checks passed; 7 API-contract tests passed. Review findings fixed before PASS: missing generic job polling, content/rubric correction routes, post moderation, notice authoring/publication, original content fields, explicit translation read and an admin post-page schema that incorrectly required one official answer.

## Residual implementation/release gates

- Jev identity/API/schema/credentials remain unknown; adapters must stay unavailable/development-stub until official documentation is supplied.
- Real OAuth, Supabase JWT/RLS, MFA/recent-auth, CSRF cookie binding, provider timeouts/retries and rate-limit behavior require integration/negative tests.
- Worker/Python implementations must generate typed clients/server models from or validate against this contract; drift is CI-failing.
- Reward ads, billing and external vendor webhooks remain disabled; adding them requires a new reviewed contract and release gate.

Gate decision: the API contract and local handler boundary are implemented and tested. Production provider integration and authenticated browser verification remain explicit release gates.
