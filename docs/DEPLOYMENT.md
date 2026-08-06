# Deployment & persistence

## Hosted staging (API + worker + PostgreSQL)

The staging stack in `docker-compose.staging.yml` builds the React application
into the API image and runs the API, scheduled alert worker, and PostgreSQL as
separate services.

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
| `MARKET_HELM_RATE_LIMIT_ENABLED` | Dashboard backend | Enables API rate limiting; defaults on when database mode is enabled |
| `MARKET_HELM_RATE_LIMIT_GLOBAL` | Dashboard backend | Per-client API requests/minute (default `120`) |
| `MARKET_HELM_RATE_LIMIT_LOGIN` | Dashboard backend | Login attempts/client/minute (default `10`) |
| `MARKET_HELM_RATE_LIMIT_REGISTER` | Dashboard backend | Registrations/client/hour (default `5`) |
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

1. **Host** — VPS (Hetzner, DigitalOcean) or PaaS (Fly.io, Railway) with a **persistent volume** for `DATA_DIR`.
2. **Deploy app** — `market-helm-web` (Docker or `pip install` + process manager); set `FINNHUB_API_KEY` and `CORS_ORIGINS`.
3. **Daily tracker** — cron or scheduler once per day (`market-helm`).
4. **Alert worker** — run `market-helm alerts run --loop` (systemd, Docker sidecar, or `scripts/run-alert-worker.ps1` on Windows) so alerts fire without opening the dashboard.
5. **Email (production)** — register a domain, verify it with SendGrid (or use Mailgun / SES SMTP), set `ALERT_EMAIL_PROVIDER` and provider secrets on the host — see [Transactional alert email](#transactional-alert-email). Users only enter their **To** address in Helmtower.
6. **Secrets** — all API keys in host env or secret manager; never commit `.env`.
7. **Smoke test** — Helmtower **Send test**, then confirm an alert delivers with the dashboard stopped and the worker running.

Roadmap context: [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## Future: hosting and **automated trading** (not implemented yet)

This repo today is **analysis + dashboard + alerts**. It does **not** place orders. The **product direction** (monitor → suggest → execute, multi-user) is in [PROJECT_STATUS.md](PROJECT_STATUS.md#product-vision). If you later add **automated buy/sell**:

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

For alert evaluation on a schedule (independent of dashboard access), use `market-helm alerts run --loop` — see [ALERTING_DESIGN.md](ALERTING_DESIGN.md).

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
