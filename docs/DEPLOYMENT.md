# Deployment & persistence

## Hosted staging (API + worker + PostgreSQL)

The staging stack in `docker-compose.staging.yml` builds the React application
into the API image and runs the API, scheduled alert worker, and PostgreSQL as
separate services. Named volumes persist PostgreSQL and the shared `DATA_DIR` used
by both application processes.

1. Copy `.env.staging.example` to `.env.staging` and replace every placeholder.
2. Set `POSTGRES_PASSWORD` in the host environment (never commit it).
3. Validate with `docker compose -f docker-compose.staging.yml config`.
4. Start with `docker compose -f docker-compose.staging.yml up -d --build`.
5. Put a TLS reverse proxy in front of `127.0.0.1:8000` and add its IP/CIDR to
   `MARKET_HELM_TRUSTED_PROXY_CIDRS`.
6. Verify `/health/live`, `/health/ready`, `/health/worker`, and `/metrics`, then test registration
   and the email-verification link against the public staging hostname.

`/health/live` proves the API process is alive. `/health/ready` returns 503 when
the database is unavailable or migrations are incomplete and includes the latest
worker heartbeat when one exists.

### Staging acceptance harness

After the stack is reachable, run the credential-free operational checks:

```bash
python scripts/staging_acceptance.py \
  --base-url https://staging.example.com \
  --report staging-acceptance.json
```

The harness requires HTTPS except for loopback development URLs. It verifies API
liveness, database readiness and schema version, a fresh worker heartbeat,
Prometheus metrics, and the hosted authentication boundary. The JSON report
contains check results and timings but no credentials; keep generated reports as
deployment evidence rather than committing them.

To prove write isolation, prepare two **dedicated, verified staging accounts**.
Their alert configurations must be empty. Supply credentials through the process
environment so passwords do not appear in shell history:

```bash
export MARKET_HELM_STAGING_TENANT_A_EMAIL=acceptance-a@example.com
export MARKET_HELM_STAGING_TENANT_A_PASSWORD='...'
export MARKET_HELM_STAGING_TENANT_B_EMAIL=acceptance-b@example.com
export MARKET_HELM_STAGING_TENANT_B_PASSWORD='...'
python scripts/staging_acceptance.py \
  --base-url https://staging.example.com \
  --tenant-check \
  --report staging-acceptance.json
```

The tenant check refuses non-empty accounts, creates two distinct log-only
watches, confirms config/index/dry-run isolation, and restores both configurations
to their original empty state. It never sends email or webhooks. A failed cleanup
is reported as a failed acceptance check and must be handled before reusing the
accounts.

`--skip-worker` is available for diagnosing a stack before its worker starts, but
a report produced with that option is marked `incomplete`, exits nonzero, and is
not sufficient for staging sign-off.

Pass `--ingress-origin https://staging.example.com` to additionally require a
correlation ID, exact-origin credentialed CORS, rejection of an untrusted origin,
and HSTS on HTTPS. Disposable tenant bootstrapping is available only on loopback:

```bash
python scripts/staging_acceptance.py \
  --base-url http://127.0.0.1:8000 \
  --ingress-origin http://127.0.0.1:8000 \
  --tenant-check --bootstrap-loopback-tenants
```

### Operational readiness drills

The `Hosted staging readiness` workflow is the repeatable repository gate. It
builds the real images, starts API + worker + PostgreSQL, runs operational/ingress/
tenant checks, applies a bounded load baseline, restores PostgreSQL and shared
market data, restarts the database and worker, and publishes credential-free JSON
evidence. Run it locally before changing deployment behavior and trigger it
manually after infrastructure changes.

For an environment-specific capacity baseline:

```bash
python scripts/staging_load.py \
  --base-url https://staging.example.com \
  --requests 100 --concurrency 10 \
  --max-error-rate 0 --max-p95-ms 1000 \
  --report staging-load.json
```

This deliberately defaults to the read-only readiness endpoint, exercising a
database connection without mutating tenant data. Raise traffic gradually and set
thresholds from the service's actual SLO; do not turn the tool into an unapproved
stress test against a shared host.

### Backup and restore runbook

Back up **both** persistence layers as one recovery set:

1. Take a managed PostgreSQL snapshot or custom-format `pg_dump`.
2. Archive the persistent `DATA_DIR` at the same logical time.
3. Record application version, schema version from `/health/ready`, timestamps,
   checksums, encryption/key reference, and retention expiry with the artifacts.
4. Restore PostgreSQL into a newly named database—never over the active database.
5. Restore `DATA_DIR` into a new empty path, start one API and one worker against
   the restored stores, and run `staging_acceptance.py`.
6. Compare user/config/migration counts and a sample of dated market files before
   declaring the recovery point usable. Remove the drill resources afterward.

The compose readiness workflow demonstrates these mechanics with a disposable
database and volume. A managed staging sign-off must additionally use the cloud
provider's snapshot/PITR process, TLS settings, and credentials because a local
container cannot prove those controls.

Default retention unless a stricter policy applies:

- encrypted daily PostgreSQL + `DATA_DIR` recovery sets for 30 days;
- encrypted weekly recovery sets for 12 weeks;
- application logs for 14 days and metrics for 30 days;
- readiness reports for at least 14 days and through the next deployment; and
- delivery history is already bounded to the newest 100 records per user.

Test one restore monthly and after database/schema changes. Alert on a missed
backup, failed checksum, expired encryption key, or failed restore drill.

### Monitoring and incident runbook

Scrape `/metrics` and probe `/health/live`, `/health/ready`, and `/health/worker`
from outside the host. Preserve `X-Request-ID` in proxy and application logs.
Recommended pages are: liveness unavailable for 2 minutes, readiness unavailable
for 5 minutes, worker unhealthy for two evaluation intervals, HTTP 5xx above 2%
for 5 minutes, or backup/restore evidence overdue.

Respond in this order:

1. **Liveness failure:** stop rollout, inspect proxy/container logs, and roll back
   the application image if the previous release is healthy.
2. **Readiness/database failure:** stop writes and workers, check provider health,
   connection/TLS limits, and schema version; fail over only through the managed
   database procedure, then rerun acceptance.
3. **Worker failure:** keep the API online, stop duplicate workers, restart one
   worker, and verify a fresh heartbeat plus queued-job progress before scaling.
4. **Provider failure:** pause alert delivery, retain queued jobs, check provider
   status/credentials/sender-domain records, then resume and inspect retry results.
5. **Suspected data loss:** freeze writes, preserve logs, restore the newest
   verified recovery set into new resources, validate it, then perform a deliberate
   cutover with a documented rollback target.

### External staging sign-off

Repository automation cannot prove controls owned by a hosting or email provider.
Complete this operator-owned TODO in order after the staging-readiness PR merges.
Never put provider credentials in an issue, PR, report, or committed environment
file; use the selected platform's secret manager.

#### External staging execution TODO

##### 1. Record decisions and ownership

- [ ] Choose the staging hostname and confirm who controls its DNS.
- [ ] Choose the application host, managed PostgreSQL provider, region, and budget.
- [ ] Choose SendGrid, Mailgun, or SES and the sender domain/address.
- [ ] Choose the monitoring service and its email/Slack/PagerDuty destination.
- [ ] Record the availability target, database RPO/RTO, backup retention, and
  person responsible for acknowledging staging incidents.

##### 2. Add and provision the target deployment

- [ ] Add provider-specific deployment configuration or infrastructure-as-code;
  the checked-in compose stack is the portable reference, not proof of a managed
  deployment.
- [ ] Provision secret storage and inject credentials without committing them.
- [ ] Provision persistent shared `DATA_DIR` storage for the API and worker.
- [ ] Deploy the same reviewed application image as separate API and worker
  services, then record the image digest and application version.

##### 3. Sign off managed PostgreSQL

- [ ] Provision PostgreSQL 16 with encryption at rest, TLS required, restricted
  networking, least-privilege application credentials, and pooling/connection
  limits appropriate for the host.
- [ ] Enable automated snapshots and point-in-time recovery with the recorded
  retention policy.
- [ ] Run migrations and the staging acceptance/tenant checks against the managed
  database.
- [ ] Restore a snapshot/PITR point into a newly named database, compare schema and
  critical record counts, and record the measured RPO/RTO.
- [ ] Perform a controlled provider failover, rerun acceptance, and save provider
  event IDs and recovery timings.

##### 4. Sign off public DNS and TLS

- [ ] Create the staging DNS record pointing only to the intended ingress.
- [ ] Install or enable a trusted, hostname-matching certificate with automatic
  renewal; enforce HTTP-to-HTTPS redirects and HSTS.
- [ ] Set `MARKET_HELM_PUBLIC_URL`, `CORS_ORIGINS`, and the exact trusted-proxy
  CIDRs for the deployed ingress.
- [ ] Run `staging_acceptance.py --ingress-origin ...` against the public HTTPS URL
  and save its JSON report plus certificate/DNS evidence.

##### 5. Sign off transactional email

- [ ] Authenticate the sender domain with provider-supplied SPF/DKIM records and
  publish a DMARC policy.
- [ ] Store a restricted provider key and configure `ALERT_EMAIL_PROVIDER` plus
  `ALERT_EMAIL_FROM`.
- [ ] Receive and complete registration verification and password-reset links;
  confirm both use `MARKET_HELM_PUBLIC_URL`.
- [ ] Deliver a real alert while the dashboard is closed and record the provider
  message ID and inbox authentication results.
- [ ] Trigger a controlled rejection and confirm retries/failure details appear in
  MarketHelm delivery history without leaking credentials.

##### 6. Sign off external monitoring and release evidence

- [ ] Probe `/health/live`, `/health/ready`, and `/health/worker` from outside the
  host and collect `/metrics` through an appropriately restricted path.
- [ ] Configure the runbook thresholds and notification destination.
- [ ] Stop the staging worker and API in controlled drills; confirm alerts arrive,
  are acknowledged, and send recovery notifications after restoration.
- [ ] Attach DNS/TLS results, database restore/failover evidence, email message IDs,
  monitoring incident IDs, image digest, and acceptance/load JSON reports to the
  staging release record.
- [ ] Review least privilege, secret rotation, backup retention, and rollback;
  obtain the named operator's final staging sign-off.

Until those artifacts exist for a specific environment, the code is staging-ready
but that environment is not approved for production.

### Hosted-mode configuration

Hosted mode requires a database URL and a stable signing secret. SQLite is useful
for development; PostgreSQL is recommended for a deployed service:

```bash
export MARKET_HELM_DATABASE_URL=sqlite:////path/to/markethelm.db
export MARKET_HELM_AUTH_SECRET=change-me-in-production-min-16-chars

# Hosted alternative:
export MARKET_HELM_DATABASE_URL=postgresql://user:password@host:5432/markethelm
```

When `MARKET_HELM_DATABASE_URL` is unset, the application remains in local file
mode. Market data stays in `DATA_DIR` in both modes; the database stores accounts,
sessions, per-user alert settings, jobs, and delivery outcomes.

The account API under `/api/auth` includes registration, login/logout, current-user
lookup, email-verification request/confirmation, password-reset
request/confirmation, password change, and account deletion. Account email links
require `MARKET_HELM_PUBLIC_URL` plus a configured platform email provider.

Schema migrations run automatically at startup and fail closed if the database has
an unknown newer version. Before production, exercise the PostgreSQL integration
gate documented in [ARCHITECTURE.md](ARCHITECTURE.md) and verify managed backups,
restore, pooling, TLS, and worker concurrency in staging.

This project runs **locally** and can run **on a host** (VPS, PaaS, containers) the same way: application code is deployed; **market data and projections stay on disk** (or, in the future, in a database) configured via environment variables—not committed to git.

---

## What gets deployed vs what stays private

| | In git | On the server (never in git) |
|---|--------|------------------------------|
| Application code | Yes | Built from git |
| `data/*.csv`, `data/*.json` | **No** (see `.gitignore`) | Written at runtime by the tracker / dashboard |
| API keys (`FINNHUB_API_KEY`, broker keys, etc.) | **No** | Injected env vars or host secret store |

---

## Persistence: `DATA_DIR`

The tracker and dashboard **read and write** CSV/JSON under a directory that defaults to **`data/`** at the project root.

- **Local dev:** usually nothing to set; `data/` is created when you run the tracker.
- **Deployed:** set **`DATA_DIR`** to an **absolute path** on **persistent storage** (attached volume, mounted disk).

If you omit persistence, containers that restart **lose** history unless you restore backups or re-fetch.

**Backend (dashboard):** `dashboard/backend` resolves data via `DATA_DIR` (see `dashboard/backend/services/data_loader.py`). If unset, it uses the repo’s `data/` folder relative to the project root.

**Example (Linux):**

```bash
export DATA_DIR=/var/lib/market-helm/data
```

Point your process manager (systemd, Docker, etc.) at that environment.

---

## Environment variables (reference)

| Variable | Used by | Purpose |
|----------|---------|---------|
| `DATA_DIR` | Tracker, dashboard backend | Path to `daily_data_*.csv`, `projections_*.csv`, `summary_*.json` |
| `FINNHUB_API_KEY` | Tracker CLI | Market data (required for live fetches) |
| `CORS_ORIGINS` | Dashboard backend | Comma-separated origins allowed in browser (e.g. `https://app.example.com`) |
| `VITE_API_URL` | Dashboard frontend (build time) | Public URL of the API (e.g. `https://api.example.com`) |
| `MARKET_HELM_DATABASE_URL` | API, worker | Enables hosted mode; SQLite for development or PostgreSQL for hosted use |
| `MARKET_HELM_AUTH_SECRET` | Dashboard backend | Required hosted session-signing secret; minimum 16 characters |
| `MARKET_HELM_PUBLIC_URL` | Dashboard backend | Safe public base URL for email verification and password-reset links |
| `MARKET_HELM_REQUIRE_EMAIL_VERIFICATION` | Dashboard backend | Require verified email before protected hosted operations |
| `MARKET_HELM_RATE_LIMIT_ENABLED` | Dashboard backend | Enables API rate limiting; defaults on when database mode is enabled |
| `MARKET_HELM_RATE_LIMIT_GLOBAL` | Dashboard backend | Per-client API requests/minute (default `120`) |
| `MARKET_HELM_RATE_LIMIT_LOGIN` | Dashboard backend | Login attempts/client/minute (default `10`) |
| `MARKET_HELM_RATE_LIMIT_REGISTER` | Dashboard backend | Registrations/client/hour (default `5`) |
| `MARKET_HELM_RATE_LIMIT_AUTH_EMAIL` | Dashboard backend | Verification/reset email requests/client/hour (default `5`) |
| `MARKET_HELM_RATE_LIMIT_EXPENSIVE` | Dashboard backend | Expensive write requests/client/minute (default `10`) |
| `MARKET_HELM_TRUSTED_PROXY_CIDRS` | Dashboard backend | Comma-separated proxy CIDRs allowed to supply `X-Forwarded-For` |
| `ALERT_WEBHOOK_URL` | Tracker (alerts) | Default webhook when rules use `webhook` without per-rule `url` |
| `ALERT_WEBHOOK_FORMAT` | Tracker (alerts) | `json`, `slack`, or `discord` webhook body format |
| `DISCORD_WEBHOOK_URL` | Tracker (alerts) | Default Discord incoming webhook URL when a rule has no `webhook_url` |
| `MARKET_HELM_ALERTS_CONFIG` | Tracker (alerts) | Optional path to `alerts.json` (default `~/.market-helm/alerts.json`) |
| `SMTP_HOST` | Tracker (alerts) | SMTP server for `email` notifications |
| `SMTP_PORT` | Tracker (alerts) | SMTP port (default `587`) |
| `SMTP_USER` | Tracker (alerts) | SMTP username |
| `SMTP_PASSWORD` | Tracker (alerts) | SMTP password or app password |
| `ALERT_EMAIL_TO` | Tracker (alerts) | Default recipients for `email` notifications |
| `ALERT_EMAIL_FROM` | Tracker (alerts) | Platform **From** address (`alerts@yourdomain.com`); required for SendGrid/Mailgun |
| `ALERT_EMAIL_PROVIDER` | Tracker (alerts) | `smtp` (default), `sendgrid`, or `mailgun`; auto-detected when API keys are set |
| `SENDGRID_API_KEY` | Tracker (alerts) | SendGrid API key when `ALERT_EMAIL_PROVIDER=sendgrid` |
| `MAILGUN_API_KEY` | Tracker (alerts) | Mailgun API key when `ALERT_EMAIL_PROVIDER=mailgun` |
| `ALERT_DELIVERY_MAX_ATTEMPTS` | Tracker (alerts) | Total send attempts per notification (default `3`) |
| `ALERT_DELIVERY_RETRY_BASE_SECONDS` | Tracker (alerts) | Initial backoff delay between retries (default `1`) |
| `ALERT_DELIVERY_RETRY_MAX_SECONDS` | Tracker (alerts) | Max backoff delay cap (default `8`) |
| `MAILGUN_DOMAIN` | Tracker (alerts) | Mailgun sending domain (e.g. `mg.yourdomain.com`) |
| `MAILGUN_API_BASE` | Tracker (alerts) | Optional; default `https://api.mailgun.net` (EU: `https://api.eu.mailgun.net`) |

**Dev vs product email:** SMTP env vars suit **self-host / operator** mail (e.g. personal Gmail). For production, use a transactional provider with a verified domain — see [Transactional alert email](#transactional-alert-email) below.

Never commit values; use your host’s secret manager or encrypted env.

### API rate limiting

Hosted database mode enables rate limiting automatically. Counters are stored in
SQLite or PostgreSQL so PostgreSQL deployments share limits across every API
instance. File mode remains unlimited unless `MARKET_HELM_RATE_LIMIT_ENABLED=true`;
in that mode counters are process-local and intended only for development.

The API returns `429 Too Many Requests` with `Retry-After` and
`X-RateLimit-*` response headers. If the shared rate-limit database is unavailable,
hosted API requests fail closed with `503` instead of silently bypassing limits.

Do not trust forwarded client headers by default. When a known load balancer or
reverse proxy connects directly to MarketHelm, set `MARKET_HELM_TRUSTED_PROXY_CIDRS`
to only that proxy network. The middleware walks `X-Forwarded-For` from right to
left and selects the first untrusted hop, preventing a client-supplied prefix from
bypassing per-client limits.

---

## Transactional alert email

Helmtower users only enter their **To** address. The platform operator configures **how** email is sent via environment variables (never in git).

### Provider selection

Set `ALERT_EMAIL_PROVIDER` explicitly, or omit it and let MarketHelm auto-detect from API keys:

| Provider | When to use | Required env |
|----------|-------------|--------------|
| **SMTP** (default) | Dev, self-host, or **AWS SES SMTP relay** | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_FROM` or `SMTP_USER` |
| **SendGrid** | Hosted product with verified sender domain | `SENDGRID_API_KEY`, `ALERT_EMAIL_FROM` |
| **Mailgun** | Hosted product with Mailgun domain | `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `ALERT_EMAIL_FROM` |

Users still set `email_to` in Helmtower (or `ALERT_EMAIL_TO` as a default). Secrets stay in the host environment only.

### SendGrid example

```bash
export ALERT_EMAIL_PROVIDER=sendgrid
export SENDGRID_API_KEY=SG.xxxx
export ALERT_EMAIL_FROM="MarketHelm Alerts <alerts@yourdomain.com>"
```

Verify the sender domain in SendGrid (SPF/DKIM) before going live.

### Mailgun example

```bash
export ALERT_EMAIL_PROVIDER=mailgun
export MAILGUN_API_KEY=key-xxxx
export MAILGUN_DOMAIN=mg.yourdomain.com
export ALERT_EMAIL_FROM="MarketHelm Alerts <alerts@yourdomain.com>"
# EU region:
# export MAILGUN_API_BASE=https://api.eu.mailgun.net
```

### AWS SES (SMTP relay)

SES works with the **SMTP** provider — no separate integration required:

```bash
export ALERT_EMAIL_PROVIDER=smtp
export SMTP_HOST=email-smtp.us-east-1.amazonaws.com
export SMTP_PORT=587
export SMTP_USER=your-ses-smtp-username
export SMTP_PASSWORD=your-ses-smtp-password
export ALERT_EMAIL_FROM="MarketHelm Alerts <alerts@yourdomain.com>"
```

Generate SMTP credentials in the AWS SES console and verify your domain first.

### Test delivery

```bash
market-helm alerts test <alert-id>
```

Or use **Send test** in Helmtower (`/alerts`). The test uses the same provider as production alerts.

---

## Typical deployment layout

1. **Backend** — Run FastAPI (`uvicorn` or `python main.py`) with `DATA_DIR` and `FINNHUB_API_KEY` set.
2. **Frontend** — Build `dashboard/frontend` (`npm run build`) and serve `dist/` from a static host (or the same reverse proxy).
3. **Scheduler** — Run the daily tracker on a schedule (cron, GitHub Actions with self-hosted runner, or the platform’s scheduler) **or** use the dashboard “Fetch New” flow if you only trigger manually.

**CORS:** set `CORS_ORIGINS` to your frontend origin so the browser can call the API.

---

## When you go live

Use this when moving from **local dev** to a **public host**. For day-to-day development, Gmail SMTP in `.env` is enough — skip this section until you deploy.

1. **Host and ingress** — provision TLS, a persistent `DATA_DIR`, and an explicitly trusted reverse-proxy CIDR.
2. **Database** — use managed PostgreSQL for hosted mode; set `MARKET_HELM_DATABASE_URL`, verify migrations, pooling, TLS, backups, and restore.
3. **Deploy API and worker** — run `market-helm-web` plus a separate `market-helm alerts run --loop` process using the same database and secrets.
4. **Auth** — set `MARKET_HELM_AUTH_SECRET`, `MARKET_HELM_PUBLIC_URL`, and email-verification policy; test registration, verification, reset, password change, logout, and deletion.
5. **Daily tracker** — schedule `market-helm` and persist its shared market-data output.
6. **Email** — verify a sender domain and configure SendGrid, Mailgun, or SES SMTP. Users only enter their recipient address in Helmtower.
7. **Operations** — configure rate limits/proxies, collect `/metrics`, and monitor `/health/ready` plus `/health/worker`.
8. **Secrets** — keep all credentials in the host secret manager; never commit `.env`.
9. **Staging proof** — test cross-tenant isolation, a real alert with the dashboard stopped, provider failures/retries, backup/restore, and worker recovery before public traffic.

Roadmap context: [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## Future: **automated trading** (not implemented)

This repo today is **analysis + dashboard + alerts**. It does **not** place orders.
The current product direction and capability matrix are in
[PROJECT_STATUS.md](PROJECT_STATUS.md#product-direction). If you later add
**automated buy/sell**:

1. **Broker API** — You need a broker that exposes **order placement** (e.g. Alpaca, Interactive Brokers, Tradier). Finnhub is **market data**, not a substitute for execution.
2. **Secrets** — Trading keys must live only in **host secrets**; rotate and scope to paper vs live.
3. **Persistence** — Use a **database** (e.g. PostgreSQL) for orders, positions, and audit logs—**before** trusting real money.
4. **Safety** — Paper trading first, hard limits (max position, max loss), kill switch, full logging.

This is **not legal or financial advice**; follow your broker’s terms and applicable regulations.

---

## Docker (CLI tracker)

Build and run the daily tracker in a container:

```bash
docker build -t market-helm:latest .
docker run --rm -e FINNHUB_API_KEY=your-key market-helm:latest
# Or: docker run --rm --env-file .env market-helm:latest
```

Mount persistent data:

```bash
docker run --rm --env-file .env \
  -v /var/lib/market-helm/data:/app/data \
  -v /var/lib/market-helm/logs:/app/logs \
  market-helm:latest
```

### Docker Compose

```yaml
services:
  market-helm:
    build: .
    environment:
      - FINNHUB_API_KEY=${FINNHUB_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

---

## Scheduled runs

Use cron (Linux/Mac), Task Scheduler (Windows), or systemd to run once per day.

**Cron example:**

```bash
0 9 * * * docker run --rm -e FINNHUB_API_KEY=$(cat /path/to/key) market-helm:latest >> /var/log/market-helm.log 2>&1
```

For alert evaluation on a schedule (independent of dashboard access), use
`market-helm alerts run --loop`. Alert component boundaries and unsupported rule
types/channels are documented in [ARCHITECTURE.md](ARCHITECTURE.md#alert-workflow).

---

## Kubernetes

Use `k8s/market-helm-cronjob.yaml` as a CronJob. Create secrets first:

```bash
kubectl create secret generic market-helm-secrets \
  --from-literal=FINNHUB_API_KEY=your-key \
  --from-literal=OPENAI_API_KEY=your-key
```

Mount a persistent volume for `DATA_DIR` so history survives pod restarts.

---

## Cloud platforms

Common patterns:

- **AWS** — ECS task + EventBridge schedule; secrets in Secrets Manager.
- **GCP** — Cloud Run job + Cloud Scheduler; secrets in Secret Manager.
- **Azure** — Container Instances + Logic Apps; secrets in Key Vault.

Store API keys in the platform secret manager; never bake them into images.

---

## Security

- Never commit keys; `.env` is gitignored.
- Use secret stores in production (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault).
- Rotate keys periodically; audit Finnhub usage at <https://finnhub.io/dashboard>.

---

## Related

- [PROJECT_STATUS.md](PROJECT_STATUS.md) — roadmap and future execution notes  
- [Dashboard README](../dashboard/README.md) — local dev, env vars  
- [USAGE.md](USAGE.md) — CLI entry points and output files  
- [Contributing](../CONTRIBUTING.md) — development workflow
