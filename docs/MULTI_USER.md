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
| **4 — Helmtower UI** | Sign-in / sign-up screens; attach token to API calls | Planned |
| **5 — Worker** | Evaluate all users' enabled watches on schedule | Planned |
| **6 — Production** | Postgres, password reset, rate limits, SMS/push | Planned |

Market **data** (CSV/JSON under `DATA_DIR`) stays shared platform data. Only **user preferences and alert rules** move to the database.

---

## Enabling multi-user mode (dev)

Set a SQLite database URL and auth secret:

```bash
export MARKET_HELM_DATABASE_URL=sqlite:////path/to/markethelm.db
export MARKET_HELM_AUTH_SECRET=change-me-in-production-min-16-chars
```

When `MARKET_HELM_DATABASE_URL` is **unset**, behavior is unchanged (file-backed alerts).

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

## Next (after this foundation PR)

| Priority | Work |
|----------|------|
| 1 | **Helmtower auth UI** — sign-in / sign-up; store token; send `Authorization: Bearer …` on `/api/alerts/*` |
| 2 | **Multi-user worker** — loop over all users with enabled watches; evaluate + deliver per user |
| 3 | **Per-user delivery log** — scope delivery status to authenticated user in DB mode |
| 4 | **Production** — Postgres driver, password reset, rate limits, hosted deploy docs |
