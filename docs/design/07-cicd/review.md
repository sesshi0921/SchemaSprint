# CI/CD and infrastructure review

Date: 2026-09-20. Status: **PASS for repository configuration; production deployment remains gated**.

## Scope reviewed

- `.github/workflows/ci.yml`: frontend lint/test/build, gateway typecheck and Wrangler dry-run without a container rollout, Terraform formatting/init/validation.
- `.github/workflows/deploy.yml`: manual, protected-environment deployment only; reusable CI is a prerequisite; Pages artifact build matches Terraform; Worker/container deploy is explicit opt-in; health smoke and Worker rollback are included.
- `infra/terraform/`: Cloudflare Pages project, Worker gateway shell, optional route, separate environment variables/backend examples, sensitive provider input, Supabase endpoint/secret-name references.
- `infra/cloudflare/gateway/`: typed same-origin gateway, private Container binding, Dockerfile, Wrangler environment configs.

## Checks and fixes

- Pages uses `frontend`, `npm ci`, `npm run build`, and `dist` in both Terraform and CI.
- Worker gateway rejects unsupported paths/methods and oversized bodies, removes client-spoofable identity headers, forwards only to the Container binding, and returns a truthful dependency failure.
- Container state is durable-object-backed and capped at one instance for the initial cost boundary; paid runtime and production route default to disabled.
- Environment state and values are separated; no credentials, service-role key, Terraform state, or plan is checked in. The deployment workflow requires GitHub protected environments, validates `SCHEMASPRINT_ENVIRONMENT`/paid gates, and uses Cloudflare Worker secret bindings provisioned by the documented operator step.
- Terraform uses Cloudflare provider `~> 5.24`, `fmt`/`validate`, and an encrypted remote-state/lock configuration supplied at init rather than committed.
- Wrangler dry-run succeeded with `--containers-rollout=none` for all three configs using the repository-root image context; local Docker was unavailable, so image build/rollout was not executed.

## Local Docker preview

This repository includes a local-only compose preview at `infra/docker-compose.yml`. It builds the same Python/Rust gateway image, serves the built PWA through Nginx, and starts PostgreSQL with a minimal local Auth-role shim before the checked-in migration. It is not a Supabase replacement and does not deploy anything.

```sh
cp infra/local/.env.example infra/local/.env
docker compose --env-file infra/local/.env -f infra/docker-compose.yml up --build
curl --fail http://localhost:8080/healthz
```

Open `http://localhost:8080/`. Stop with `Ctrl-C`; remove the local database volume only when intentionally resetting state: `docker compose --env-file infra/local/.env -f infra/docker-compose.yml down -v`. The example values are development-only and must never be reused in a hosted environment.

## Remaining release gates

1. Obtain owner-approved budget, region, provider data-processing terms, and Workers Paid approval before enabling Containers.
2. Configure per-environment least-privilege Cloudflare tokens, Cloudflare Worker secret bindings (see `infra/terraform/README.md`), protected reviewers, encrypted remote state, lock table, and backups.
3. Build the `linux/amd64` image with Docker/Workers Builds; verify cold start, bounded concurrency, request limits, graceful dependency failure, logs, and rollback.
4. Validate real Supabase Auth JWT/RLS/MFA behavior in staging; run migration backup/restore and deletion-ledger drills.
5. Configure production domain/route and monitoring/runbook ownership only after security, accessibility, E2E, legal, and vendor gates pass.

No Terraform apply, Pages upload, Worker deploy, container rollout, provider call, or local Docker build was performed in this review (Docker is not available in the current shell).
