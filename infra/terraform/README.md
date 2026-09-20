# SchemaSprint Cloudflare infrastructure

Terraform manages the Cloudflare Pages project, Worker gateway shell, and optional API route. The Worker version/container image is deployed by the authorized Wrangler workflow because the image build and container rollout are not transactional and secrets must not enter Terraform state; see `infra/cloudflare/gateway/wrangler.*.jsonc`.

## Environments and state

Each environment uses a separate encrypted remote S3-compatible state object and lock table. Copy, review, and keep the following files outside Git:

```sh
terraform -chdir=infra/terraform init \
  -backend-config=backend/staging.s3.tfbackend \
  -reconfigure
terraform -chdir=infra/terraform plan \
  -var-file=environments/staging.tfvars
```

The committed `*.example` files contain placeholders only. `terraform.tfvars`, `*.tfbackend`, state, and plan files are ignored. Use a short-lived Cloudflare API token through `CLOUDFLARE_API_TOKEN` or `TF_VAR_cloudflare_api_token`; never add it to a variable file or workflow log.

The CI `terraform` job runs `fmt`, `init -backend=false`, and `validate`. It does not apply infrastructure. Apply is a separately authorized operation after review.

## Required Cloudflare permissions

The token used by Terraform needs only the account/zone resources managed here:

- `Pages Read` and `Pages Write`;
- `Workers Scripts Read` and `Workers Scripts Write`;
- `Workers Routes Read` and `Workers Routes Write` when `enable_production_route=true`;
- `Account Settings Read` only if the account API requires it for Worker metadata.

Do not grant `Workers AI`, DNS edit, billing, or global administrator permissions. The deployment token used by Wrangler is a separate environment secret and is scoped to the Pages/Worker/container operations required by that environment.

## Runtime boundary

```text
Pages static PWA -> same-origin Worker gateway -> private Container (Python + Rust) -> Supabase Auth/Postgres
```

The gateway removes spoofable identity headers and forwards the user session cookie/JWT for backend revalidation. It does not expose a public origin for the container. The database DSN is injected by the approved Worker secret mechanism, never by Terraform or a client binding.

`enable_paid_runtime=false` and `enable_production_route=false` are safe defaults. Cloudflare Containers require Workers Paid and Docker-compatible tooling for a Dockerfile image. Terraform rejects a development paid runtime and rejects an enabled route unless the zone, exact API hostname, and matching HTTPS `api_base_url` are present. Set the paid gate only after owner budget, vendor/data-processing, staging cold-start/load, backup/rollback, and security release gates pass. The protected deployment workflow independently verifies the same paid gate before it can roll out a container.

## Deploy alignment

`cloudflare_pages_project.build_config` is intentionally identical to CI:

```text
working directory: frontend
install: npm ci
build: npm run build
artifact: dist
```

The manual, reviewed `.github/workflows/deploy.yml` uploads that `frontend/dist` artifact to the Terraform-created Pages project. `VITE_API_BASE_URL` is baked into the build from the Terraform `api_base_url` contract (or `/api` for same-origin routing); the workflow refuses an unconfigured value. It deploys the Worker/container only when the operator explicitly selects `deploy_container=true` in a protected GitHub environment and the environment's `ENABLE_PAID_RUNTIME=true` gate agrees. Wrangler configs and the container Dockerfile are under `infra/cloudflare/gateway`; `image_build_context=../../..` makes the Docker context the repository root so the checked-in backend/rust package is included.

Configure these non-secret variables in each protected GitHub environment and keep them aligned with the Terraform plan: `ENVIRONMENT` (`staging` or `production`), `ENABLE_PAID_RUNTIME` (`true` only after approval), `PAGES_PROJECT_NAME`, `VITE_API_BASE_URL` (`/api` or the exact HTTPS gateway base), `SMOKE_WEB_URL`, and (for container deploy/rollback) `SMOKE_API_URL`. The checked-in Wrangler `PAID_RUNTIME` marker is the second, reviewable gate: leave it `false` (and Terraform `enable_paid_runtime=false`) for the MVP; only an approved paid-runtime change may set all three gates to `true`.

A container deployment can activate the Worker before image push/rollout completes. After every authorized deploy, check Worker status, container rollout/logs, `/healthz`, and a representative authenticated API request. On failure, stop promotion, retain the prior Worker/container version, and roll forward or restore the last known-good immutable artifact; do not destroy the database.

## Secrets and Supabase

Provision these exact names as Cloudflare Worker secrets through the protected deployment workflow before a real container deployment (the values are never Terraform variables or Pages bindings):

- `DATABASE_DSN`;
- `SESSION_PEPPER`;
- `CSRF_KEY`;
- `ALLOWED_ORIGIN`;
- optional `JEV_MODE`, `JEV_BASE_URL`, and `JEV_API_KEY` when external Jev is approved.
- optional `JEV_MODEL`, `JEV_TIMEOUT_SECONDS`, and `JEV_MAX_RETRIES` when external Jev is approved;
- optional `LLM_MODE`, `GROQ_API_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, and `GROQ_TIMEOUT_SECONDS` when Groq feedback generation is approved. The Groq key is server-only.

`ENVIRONMENT` is a non-secret Wrangler variable and must match the selected protected environment. The Worker passes only these bindings to the private container at startup. Never print them, place them in tfvars, or expose them to the frontend; the database DSN is the only Supabase/PostgreSQL connection material the backend needs.

Before selecting `deploy_container=true`, provision the bindings from a protected operator shell (the GitHub workflow intentionally does not echo or transport secret values):

```sh
config="infra/cloudflare/gateway/wrangler.production.jsonc"
printf '%s' "$DATABASE_DSN" | infra/cloudflare/gateway/node_modules/.bin/wrangler secret put DATABASE_DSN --config "$config"
printf '%s' "$SESSION_PEPPER" | infra/cloudflare/gateway/node_modules/.bin/wrangler secret put SESSION_PEPPER --config "$config"
printf '%s' "$CSRF_KEY" | infra/cloudflare/gateway/node_modules/.bin/wrangler secret put CSRF_KEY --config "$config"
printf '%s' "$ALLOWED_ORIGIN" | infra/cloudflare/gateway/node_modules/.bin/wrangler secret put ALLOWED_ORIGIN --config "$config"
```

Use the staging config for staging, and keep the shell variables in an approved secret manager. The workflow validates that the protected environment has corresponding secret entries before rollout but cannot prove Cloudflare secret storage without performing a live provider call.

Rotate on exposure and verify that logs, Pages assets, Terraform plans/state, and client bundles contain no secret values.
