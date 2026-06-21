# Project status & roadmap

**Last updated:** 2026-06-17 — transactional email providers + alert worker on `main`; reliability/UI delivery status next

This file is the **single place** for “where we are,” “what’s next,” and **gaps** (skipped or deferred work). Other READMEs link here for details. **Hosting and go-live steps:** [DEPLOYMENT.md](DEPLOYMENT.md#when-you-go-live).

---

## Product vision

**Goal:** Build a **real product** that anyone can use—not a tool only a single operator configures on their machine.

Users should be able to **sign up, enter email (and later phone/push), pick what to watch, and receive alerts** without editing JSON, cloning a repo, or SSH-ing into a server. That is the target experience (similar to well-known consumer finance apps).

**Phased capability:**

1. **Monitor** the market on a schedule (screening, data fetch, summaries).
2. **Suggest** what to buy or sell (projections, recommendations, opportunities, alerts).
3. **Execute** trades on the user’s behalf **safely** (broker API, limits, audit trail)—**not in the codebase yet**; see [DEPLOYMENT.md](DEPLOYMENT.md).
4. **Serve many users** — accounts, per-user preferences, isolated secrets, likely a **database** (not only shared flat files).

**Where we are today:** analysis + file-backed storage + dashboard for **viewing** data + **Helmtower** (price-alert UI) + alert engine with email/webhook delivery + scheduled worker CLI. JSON under `~/.market-helm/` remains **interim storage** behind the API—not the user-facing workflow.

**Disclaimer:** This is software design, not investment, legal, or tax advice. Automated trading has regulatory and broker rules; validate with professionals and your broker.

---

## Product requirements — Alerts (non‑negotiable direction)

These define what “done” looks like for alerts as a **product feature**. Local JSON is acceptable only as a **temporary storage layer** behind an API/UI—not as the user-facing workflow.

| Requirement | Target | Today |
|-------------|--------|--------|
| **Subscribe without config files** | User enters email (and later phone) in **Helmtower** | ✅ Dashboard UI (`/alerts`) |
| **No repo clone for end users** | Pip install or hosted app; preferences via UI → `~/.market-helm` | ✅ Onboarding + save via API |
| **Always-on delivery** | Background job checks rules on a schedule (not “user opened dashboard today”) | ✅ `market-helm alerts run --loop` — operator schedules on host (see [DEPLOYMENT.md](DEPLOYMENT.md#when-you-go-live)) |
| **Per-user isolation** | Each user’s rules and contact info are private | ❌ Single shared config file |
| **Test from UI** | “Send test notification” button | ✅ Per-rule test in Helmtower |
| **Accounts (later)** | Sign-in, saved preferences across devices | ❌ Planned |

**Explicitly not the product:** “One operator edits `alerts.json` and sets SMTP env vars.” CLI/env remain valid for **self-hosted dev**, but Helmtower is the primary surface for dashboard users.

---

## Production alert delivery (target)

How email (and later SMS/push) should work in a **hosted product** vs what we use **today** for dev/self-host. Provider setup (SPF, DKIM, API keys): [DEPLOYMENT.md — Transactional alert email](DEPLOYMENT.md#transactional-alert-email).

| | **Today (dev / self-host)** | **Target (hosted product)** |
|--|-----------------------------|-----------------------------|
| **Who configures delivery** | Operator in `.env` or `~/.market-helm/.env` | **Platform** ops — one provider account for the whole app |
| **From** | Often same as `SMTP_USER` (e.g. your Gmail) | **MarketHelm** `<alerts@yourdomain.com>` via SendGrid, Mailgun, or SES SMTP |
| **To** | Email saved in Helmtower (single-tenant) | **Each user’s email** from DB (multi-tenant) |
| **Secrets** | Operator’s Gmail app password in env; webhooks in `~/.market-helm/.env` | Provider API key / SMTP creds in **host secret manager only** |
| **User action** | Helmtower: email, Discord/Slack webhook, set watch, test | Same UX; platform-owned **From** and per-user **To** |

**Code today:** `ALERT_EMAIL_PROVIDER` supports **smtp** (default), **sendgrid**, and **mailgun**; users set **To** in Helmtower only.

**Why tests look like “email yourself”:** dev mode uses *your* mailbox to authenticate and *your* address as recipient. That proves delivery; it is not the end-user UX for a hosted product.

**Phased path:**

1. ~~**Foundation** — SMTP + webhook notifiers, CLI, alerts API.~~ **Shipped** (PR #142).
2. ~~**Helmtower v1** — dashboard UI; user enters **To** and rules; server delivery from env.~~ **Shipped** (PR #143).
3. ~~**Production delivery plumbing** — always-on worker CLI, transactional providers (SendGrid/Mailgun), deploy docs.~~ **Shipped** on `main` / `feat/transactional-email`.
4. ~~**Production gaps (remaining)**~~ **Shipped** — retry/backoff + delivery status in Helmtower.
5. **Hosted product** — user accounts, DB-backed rules, SMS/push.

We do **not** require each end user to create a Gmail app password or supply SMTP credentials.

---

## Snapshot

| Area | Status | Notes |
|------|--------|--------|
| CLI / daily tracker | **Stable** | Core workflows, CSV/JSON output; evaluates watch symbols on fetch |
| Web dashboard | **Active** | FastAPI + React; market views, Historical Trends, projection accuracy, **Helmtower** |
| Alerts (backend) | **Stable (v1+)** | Engine, log/webhook/email (SMTP + SendGrid/Mailgun), CLI, `/api/alerts/*`, worker |
| Alerts (product UI) | **Shipped (v1)** | Helmtower: watches, channels, live picker prices, E2E in CI |
| Historical / accuracy | **Partial** | Multi-day charts + `GET /api/history/accuracy` + UI |
| Tests | **Good coverage** | Core, dashboard, alerts API, Helmtower picker E2E |
| Hosting / deploy | **Documented** | [DEPLOYMENT.md](DEPLOYMENT.md) incl. [go-live steps](DEPLOYMENT.md#when-you-go-live) |

---

## Work in flight

**Branch:** `feat/hosted-multi-user` — SQLite storage, auth API, per-user alerts API.

| Item | Status |
|------|--------|
| SQLite schema + user accounts | Done |
| Auth API (`/api/auth/register`, `/login`, `/me`) | Done |
| Per-user alerts API when `MARKET_HELM_DATABASE_URL` set | Done |
| Helmtower sign-in / sign-up UI | Planned |
| Multi-user alert worker | Planned |

See [MULTI_USER.md](MULTI_USER.md).

---

## What’s next (recommended order)

### 1. **Hosted multi-user — follow-ups** (after this PR merges)

Foundation (storage, auth API, per-user alerts API) ships in PR on `feat/hosted-multi-user`. Remaining work:

- [ ] **Helmtower auth UI** — sign-in / sign-up screens; persist bearer token; attach `Authorization` header on alerts API calls
- [ ] **Multi-user alert worker** — evaluate all users' enabled watches on schedule (not just one file config)
- [ ] **Per-user delivery history** — move delivery log from shared file storage to DB when multi-user mode is on
- [ ] **Production hardening** — PostgreSQL, password reset, rate limits, update [AGENTS.md](../AGENTS.md) (database optional today)

See [MULTI_USER.md](MULTI_USER.md).

### 2. **Alerts — production gaps** (complete on `main`)

- [x] **Always-on worker** — `market-helm alerts run --loop` (+ `scripts/run-alert-worker.ps1`)
- [x] **Transactional email** — SendGrid/Mailgun/SMTP via `ALERT_EMAIL_PROVIDER`
- [x] **Deploy docs** — [DEPLOYMENT.md](DEPLOYMENT.md#when-you-go-live) and [transactional email](DEPLOYMENT.md#transactional-alert-email)
- [x] **Reliability** — retry/backoff for webhook/email failures (`ALERT_DELIVERY_*` env)
- [x] **Delivery status in UI** — latest per-channel outcomes on `/alerts`

**Later (same epic):** SMS/push after hosted email works.

### 3. Projection accuracy — deeper analytics

- Buckets by **confidence** band; business-day targets if needed.

### 4. Dashboard UX (general)

- Code splitting, watchlist, saved views.

### 5. Tests & services coverage

- `data_fetcher.py`, `stock_screener.py`, `index_fetcher.py`; optional full tracker integration test.

### 6. Future: execution & multi-tenant SaaS

- Broker API, order DB, auth — see [DEPLOYMENT.md](DEPLOYMENT.md) and product vision above.

---

## Recently shipped (on `main`)

1. **Delivery retry/backoff** — transient email/webhook failures with `ALERT_DELIVERY_*` env (PR #196).
2. **Scheduled alert worker** — `market-helm alerts run` / `--loop`, interval via env or flag.
2. **Helmtower (Alerts Settings UI)** — `/alerts`: watches, email + Discord/Slack, company picker with live quotes (PR #143).
3. **Alerts foundation** — SMTP email, Discord/Slack webhooks, CLI `alerts init|list|test`, user config at `~/.market-helm/` (PR #142).
4. **Docs split** — README slimmed; guides under `docs/` (PR #177).
5. **Projection accuracy** — API + Historical Trends UI.
6. **CI / release automation** — E2E smoke (incl. Helmtower picker), post-release auto-finish.

6. **Transactional email** — SendGrid/Mailgun/SMTP via `ALERT_EMAIL_PROVIDER` (PR #188).
7. **Delivery retry/backoff** — PR #196.

---

## Skipped / deferred / gaps — and how we address them

| Item | Why deferred | How we address it |
|------|----------------|-------------------|
| **Operator must schedule worker on host** | CLI exists; no managed SaaS yet | [DEPLOYMENT.md — When you go live](DEPLOYMENT.md#when-you-go-live) |
| **Email retry / delivery status in UI** | v1 proves delivery path | **§1 above** — reliability |
| **User accounts + DB** | Large scope | **§1 above** — foundation in this PR; UI + worker next |
| **Phone / SMS / push** | Email + webhook first | After hosted email works |
| **Technical rules (RSI, AND/OR)** | Scope | [ALERTING_DESIGN.md](ALERTING_DESIGN.md); after production gaps |
| **Automated trading** | Out of scope | Broker + DB + compliance; later phase |

---

## How to keep this current

- After meaningful merges, update **Last updated**, **Work in flight**, and **What’s next**.
- When a branch merges, move items from **Work in flight** to **Recently shipped**.
- Prefer **one** roadmap section in [CONTRIBUTING.md](../CONTRIBUTING.md) that points here.

---

## Related docs

- [Deployment & persistence](DEPLOYMENT.md)
- [Alerting design (full vision)](ALERTING_DESIGN.md)
- [Dashboard design](DASHBOARD_DESIGN.md)
- [Contributing](../CONTRIBUTING.md)
- [Dashboard README](../dashboard/README.md)
