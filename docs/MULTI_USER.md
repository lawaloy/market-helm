# Hosted multi-user (in progress)

**Goal:** One deployed MarketHelm instance serves many signed-in users, each with private Helmtower watches and delivery settings.

**Today (single-tenant):** one shared `alerts.json` per server / `~/.market-helm`.

---

## Phases

| Phase | Scope | Status |
|-------|--------|--------|
| **1 — Storage** | SQLite (dev) / PostgreSQL (prod later); `users` + per-user alert config JSON | Done |
| **2 — Auth API** | Register, login, session token; `GET /api/auth/me` | Done |
| **3 — Alerts API** | When multi-user enabled, `/api/alerts/*` scoped to authenticated user | Done |
| **4 — Helmtower UI** | Sign-in / sign-up screens; attach token to API calls | Done |
| **5 — Worker** | Evaluate all users' enabled watches on schedule | Done |
| **6 — Production** | Migrations, Postgres, password reset, rate limits, SMS/push | In progress |

Market **data** (CSV/JSON under `DATA_DIR`) stays shared platform data. Only **user preferences and alert rules** move to the database.

---

## Enabling multi-user mode (dev)

Set a SQLite database URL and auth secret:

```bash
export MARKET_HELM_DATABASE_URL=sqlite:////path/to/markethelm.db
export MARKET_HELM_AUTH_SECRET=change-me-in-production-min-16-chars
```

When `MARKET_HELM_DATABASE_URL` is **unset**, behavior is unchanged (file-backed alerts).

For hosted environments, use a PostgreSQL URL instead:

```bash
export MARKET_HELM_DATABASE_URL=postgresql://user:password@host:5432/markethelm
```

Both backends use the same storage API and migration history. SQLite remains the
recommended local-development backend; PostgreSQL is recommended for hosted use.
The base package includes portable Psycopg; production images must also provide
`libpq` (or explicitly install `psycopg[binary]` on a supported platform).

Run the real PostgreSQL storage integration gate locally with Docker:

```bash
docker compose -f docker-compose.postgres-test.yml up \
  --abort-on-container-exit --exit-code-from tests
docker compose -f docker-compose.postgres-test.yml down --volumes
```

The integration test creates an isolated schema, exercises migrations, users,
alert/watch persistence, and the worker job lifecycle, then drops that schema.
CI runs the same test against a PostgreSQL 16 service container on every PR.

### Schema upgrades

`init_database()` applies pending schema migrations in version order at startup.
Existing SQLite installations created before migration tracking are adopted safely:
the idempotent initial schema is applied and recorded without deleting user data.
The application fails closed when it encounters an unknown newer schema version,
which prevents an older release from silently corrupting an upgraded database.

### Auth flow

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your-password"}'

# Login → access_token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your-password"}'

# Use token on alerts routes
curl http://localhost:8000/api/alerts/config \
  -H "Authorization: Bearer <access_token>"
```

---

## Related docs

- [PROJECT_STATUS.md](PROJECT_STATUS.md#product-requirements--alerts-non‑negotiable-direction)
- [DEPLOYMENT.md](DEPLOYMENT.md) — platform email, go-live

---

## Next

| Priority | Work |
|----------|------|
| 1 | **PostgreSQL deployment verification** — exercise migrations and worker concurrency against a managed staging database |
| 2 | **Auth lifecycle** — password reset, email verification, and session invalidation |
| 3 | **Production controls** — rate limits, account controls, observability, hosted deploy docs |
