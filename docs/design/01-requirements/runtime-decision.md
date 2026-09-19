# Runtime feasibility decision

Decision date: 2026-09-20. Implementation choice, not deployment authorization.

The delivery skill requires Python service orchestration with nontrivial Rust domain logic imported as a Python extension. Preserve the product's Cloudflare/Supabase boundary: static Pages → same-origin Worker gateway → private Cloudflare Container (Python + Rust extension) → Supabase and approved providers. The Worker is the sole public application ingress, handles edge limits and routing, and forwards no trusted client-supplied identity headers. Python revalidates session/action policy; normal persistence propagates the user JWT to Supabase RLS. Privileged operations remain explicitly scoped and audited. No separate public container endpoint is exposed.

Cloudflare documents Linux/amd64 container images and Worker-managed start/sleep behavior. This provides a conventional native-extension runtime rather than assuming arbitrary PyO3 wheels execute in Python Workers' Pyodide runtime. Source: [Containers getting started](https://developers.cloudflare.com/containers/get-started/), [Python Workers packages](https://developers.cloudflare.com/workers/languages/python/packages/).

Use one bounded instance initially, idle sleep, durable job state in PostgreSQL, and no in-memory-only correctness state. Resume interrupted jobs with leases/idempotency; never hold a database transaction open over inference. Container cold start and concurrent load need measured acceptance before release. Local native Python/Rust execution remains possible without deploying infrastructure; container-image verification needs Docker, which is not currently on PATH.

## Cost boundary

Containers require Workers Paid; documented rates at review time include a USD 5 monthly plan, with separate container/Worker/Durable Object/log/network usage. This is not a free-hosting promise. Do not enable paid infrastructure until an owner budget is approved. [Official pricing](https://developers.cloudflare.com/containers/platform/pricing/).

For a basic instance, a conservative continuously active 30-day scenario is 720 GiB-hours memory and 2,880 GB-hours disk. After the documented included 25 GiB-hours and 200 GB-hours, these components are about USD 6.26 and USD 0.68 respectively, excluding CPU, base plan, Worker/DO usage, network, logs, Supabase and providers. CPU must be estimated from measured duty cycle; do not call this a total bill. Idle sleep decreases active time, not vendor minimums.

Production cost model must add measured request count/CPU, actual container active time, model tokens, translation characters, database/storage/backups, and logs/egress. All externally chargeable features remain disabled by default until budget, region and vendor terms gates pass. Security and retention controls cannot be traded away for price.
