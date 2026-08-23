# Architecture

MarketHelm has a reusable Python core, two presentation layers (CLI and web), a
React dashboard, and an optional hosted persistence/worker subsystem.

## Repository layout

```text
market-helm/
|-- main.py                         # Source-checkout CLI entry point
|-- src/
|   |-- core/                       # Configuration and logging
|   |-- services/                   # Finnhub client, index/screening/data fetch
|   |-- analysis/                   # Market analysis, projections, summaries
|   |-- storage/                    # Files, SQLite/PostgreSQL, sessions, migrations
|   |-- workflows/                  # Reusable tracker orchestration
|   |-- alerts/                     # Rules, workers, channels, delivery status
|   `-- cli/                        # `market-helm` command presentation
|-- dashboard/
|   |-- backend/                    # FastAPI routes, auth, rate limits, health
|   `-- frontend/                   # React/TypeScript SPA
|-- config/                         # Exchange, filter, and alert examples
|-- data/                           # Shared CSV/JSON/Markdown market output
|-- tests/                          # Python unit/integration/security tests
`-- scripts/                        # Build, release, worker, and validation helpers
```

Business logic belongs in `src/` so the CLI, FastAPI routes, and workers can reuse
it. The frontend communicates with FastAPI through `/api/*` routes. A production
frontend build is emitted into `dashboard/backend/static/` and served by FastAPI.

## Operating modes

### Local/self-hosted file mode

This is the default when `MARKET_HELM_DATABASE_URL` is unset.

- Market runs write dated CSV/JSON/Markdown files under `DATA_DIR`.
- Alert preferences and history use the local MarketHelm configuration directory.
- Alert API routes are intended for an operator-controlled deployment and do not
  require user accounts.
- `market-helm alerts run --loop` evaluates rules on a schedule.

### Hosted multi-user mode

Setting `MARKET_HELM_DATABASE_URL` enables SQLite or PostgreSQL persistence for
accounts and tenant-owned alert state.

- Bearer sessions protect tenant-specific API routes.
- Alert configuration, watches, jobs, and delivery history are scoped per user.
- Market data files remain shared platform inputs.
- The orchestrator creates jobs and workers claim/process them from the database.
- Versioned migrations run at startup and fail closed on an unknown newer schema.
- Rate limiting defaults on and health/readiness/worker/metrics endpoints support
  operations.

The account router provides registration, login/logout, current-user lookup,
verification request/confirmation, password-reset request/confirmation, password
change, and account deletion. Password changes invalidate other sessions. Optional
verification enforcement is controlled with
`MARKET_HELM_REQUIRE_EMAIL_VERIFICATION`.

`init_database()` applies pending migrations in version order. Older untracked
SQLite installations are adopted through the idempotent initial migration, while
an unknown newer schema version causes startup to fail closed. The PostgreSQL 16
integration gate exercises migrations, tenant storage, and the worker lifecycle:

```bash
docker compose -f docker-compose.postgres-test.yml up \
  --abort-on-container-exit --exit-code-from tests
docker compose -f docker-compose.postgres-test.yml down --volumes
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for configuration and hosted verification.

## Daily market workflow

```text
index constituents
        |
        v
lightweight quote screening -- Finnhub rate limiter/retry
        |
        v
detailed quote/profile fetch for selected symbols
        |
        v
market analysis + heuristic five-day projections
        |
        +--> dated CSV/JSON/Markdown files
        +--> dashboard history/accuracy APIs
        `--> alert evaluation snapshot
```

The workflow is batch-oriented. "Fetch New" starts the same underlying tracker
work in a background process; it is not a streaming quote service.

## Alert workflow

```text
market snapshot / selected quote
             |
             v
       rule evaluation ---- cooldown state
             |
             v
   log / email / webhook delivery
             |
             v
       delivery outcome/history
```

In hosted mode, database jobs add claim/lease semantics around evaluation so
multiple workers can process user rules without sharing in-memory tenant state.

Current conditions are price thresholds and screening matches. Current channels
are log, SMTP/SendGrid/Mailgun email, and generic/Slack/Discord webhooks. Technical
indicators, patterns, compound rules, SMS, push, and cloud queue-provider adapters
are not implemented.

| Module | Responsibility |
|--------|----------------|
| `alert_engine.py`, `alert_rules.py` | Parse and evaluate current rules |
| `alert_storage.py`, `user_alert_storage.py` | Local and tenant-scoped persistence |
| `alert_runner.py`, `alert_worker.py` | One-shot and looping evaluation |
| `alert_orchestrator.py`, `job_processor.py` | Schedule, claim, and process hosted jobs |
| `delivery_status.py` | Record per-channel outcomes |
| `notifiers/` | Email/webhook delivery and retry classification |

## Data ownership

| Data | Local mode | Hosted mode |
|------|------------|-------------|
| Market CSV/JSON/Markdown | `DATA_DIR` | Shared `DATA_DIR` |
| Alert config and history | Local JSON/files | Per-user database records |
| Accounts and sessions | Not used | Database |
| Worker jobs and outcomes | Local run state/history | Database |
| Provider credentials | Environment or local `.env` | Platform secret manager/environment |

The database is not currently a market-data warehouse. Persistence for generated
market history remains file based in both modes.

## External API limiting and retries

`src/services/api_client.py` owns Finnhub request limiting, connection reuse, retry,
and `429 Retry-After` behavior. Screening uses a quote-only request; only selected
symbols receive the more expensive detailed fetch. Configuration should stay
within the active Finnhub plan rather than relying on a hard-coded provider quota.

This limiter is separate from the dashboard's inbound API rate limiter in
`dashboard/backend/rate_limit.py`. Hosted API limits are configurable by route
class and use trusted-proxy configuration to determine the client address.

## Web/API boundaries

FastAPI groups routes by concern:

- market overview/movers, projections, stocks, summaries, and history;
- background refresh start/status/cancel;
- alert configuration, quotes, execution, tests, and delivery status;
- registration, sessions, verification, recovery, and account controls; and
- liveness, readiness, worker health, and metrics.

File mode preserves the original operator workflow. Hosted mode changes ownership
and authorization of tenant data; it does not change the shared market-data model.

## Important limitations

- Projections are heuristic and are not a validated trading model.
- Quotes and dashboard data are batch/refresh based, not WebSocket streams.
- Managed PostgreSQL, provider delivery, ingress, backups, and restore need staging
  verification even though adapters and tests exist.
- There is no broker API, order model, or automated execution path.

## Related documentation

- [Project status and test gaps](PROJECT_STATUS.md)
- [Configuration](CONFIGURATION.md)
- [Deployment](DEPLOYMENT.md)
- [Stock projections](STOCK_PROJECTIONS.md)
- [Dashboard guide](../dashboard/README.md)
