# Project status & roadmap

**Last updated:** 2026-05-21 — production alert delivery target documented; alerts foundation validated (email smoke)

This file is the **single place** for “where we are,” “what’s next,” and **gaps** (skipped or deferred work). Other READMEs link here for details.

---

## Product vision

**Goal:** Build a **real product** that anyone can use—not a tool only a single operator configures on their machine.

Users should be able to **sign up, enter email (and later phone/push), pick what to watch, and receive alerts** without editing JSON, cloning a repo, or SSH-ing into a server. That is the target experience (similar to well-known consumer finance apps).

**Phased capability:**

1. **Monitor** the market on a schedule (screening, data fetch, summaries).
2. **Suggest** what to buy or sell (projections, recommendations, opportunities, alerts).
3. **Execute** trades on the user’s behalf **safely** (broker API, limits, audit trail)—**not in the codebase yet**; see [DEPLOYMENT.md](DEPLOYMENT.md).
4. **Serve many users** — accounts, per-user preferences, isolated secrets, likely a **database** (not only shared flat files).

**Where we are today:** analysis + file-backed storage + dashboard for **viewing** data + a **partial** alert engine (backend only). The JSON config path is **interim plumbing**, not the long-term product surface.

**Disclaimer:** This is software design, not investment, legal, or tax advice. Automated trading has regulatory and broker rules; validate with professionals and your broker.

---

## Product requirements — Alerts (non‑negotiable direction)

These define what “done” looks like for alerts as a **product feature**. Local JSON is acceptable only as a **temporary storage layer** behind an API/UI—not as the user-facing workflow.

| Requirement | Target | Today |
|-------------|--------|--------|
| **Subscribe without config files** | User enters email (and later phone) in a **Settings → Alerts** UI | ❌ JSON / env only |
| **No repo clone for end users** | Pip install or hosted app; preferences under user account or `~/.market-helm` via UI | ⚠️ CLI `alerts init` only |
| **Always-on delivery** | Background job checks rules on a schedule (not “user ran CLI today”) | ❌ Runs with tracker cron only |
| **Per-user isolation** | Each user’s rules and contact info are private | ❌ Single shared config file |
| **Test from UI** | “Send test notification” button | ⚠️ CLI `alerts test` only |
| **Accounts (later)** | Sign-in, saved preferences across devices | ❌ Planned |

**Explicitly not the product:** “One operator edits `alerts.json` and sets SMTP env vars.” That remains valid for **self-hosted dev** until the UI lands, but it is **not** the experience we ship to end users.

---

## Production alert delivery (target)

How email (and later SMS/push) should work in a **hosted product** vs what we use **today** for dev/self-host. Provider-specific setup (SPF, DKIM, API keys) belongs in [DEPLOYMENT.md](DEPLOYMENT.md) when we implement hosted sending—not here.

| | **Today (dev / self-host)** | **Target (hosted product)** |
|--|-----------------------------|-----------------------------|
| **Who configures SMTP** | Operator in `.env` or `~/.market-helm/.env` | **Platform** ops — one provider account for the whole app |
| **From** | Often same as `SMTP_USER` (e.g. your Gmail) | **MarketHelm** &lt;`alerts@yourdomain.com`&gt; via transactional email (SendGrid, Mailgun, AWS SES, etc.) |
| **To** | `ALERT_EMAIL_TO` in env (often same inbox as sender during tests) | **Each user’s email** saved in Settings → Alerts (per user after accounts) |
| **Secrets** | Operator’s Gmail app password in env | Provider API key / SMTP creds in **host secret manager only** — never in user-facing config |
| **User action** | Edit JSON + env | Enter email, pick rules, tap **Test notification** |

**Why tests look like “email yourself”:** dev mode uses *your* mailbox to authenticate and *your* address as recipient. That proves delivery; it is not the end-user UX.

**Phased path:**

1. **Now** — SMTP notifier + CLI/UI storage; operator Gmail (or similar) for smoke and single-user self-host.
2. **Settings UI (next)** — user enters **To** address in dashboard; server still uses platform SMTP from env (single-tenant).
3. **Hosted product** — pick one transactional provider; fixed **From** domain; per-user **To** from DB; optional SMS/push later.

We do **not** require each end user to create a Gmail app password or supply SMTP credentials.

---

## Snapshot

| Area | Status | Notes |
|------|--------|--------|
| CLI / daily tracker | **Stable** | Core workflows, CSV/JSON output, tests for major modules |
| Web dashboard | **Active** | FastAPI + React; market views, Historical Trends, projection accuracy |
| Alerts (backend) | **In progress** | Engine + log/webhook on `main`; **branch** adds email, Slack payloads, CLI list/test/init |
| Alerts (product UI) | **Not started** | **Next milestone after** current alerts branch is tested and merged — see below |
| Historical / accuracy | **Partial** | Multi-day charts + `GET /api/history/accuracy` + UI |
| Tests | **Good coverage** | Core, dashboard, alerts; E2E smoke in CI |
| Hosting / deploy | **Documented** | [DEPLOYMENT.md](DEPLOYMENT.md) |

---

## Work in flight (validate before merge)

**Branch:** `feat/alerts-smtp-email` (not on `main` yet)

| Item | Status |
|------|--------|
| SMTP email notifier | Implemented — live email smoke passed |
| Discord webhook payload (`webhook_format: discord`) | Implemented — set `DISCORD_WEBHOOK_URL` or per-rule `webhook_url` |
| CLI `market-helm alerts init\|list\|test` | Implemented |
| User config path `~/.market-helm/alerts.json` | Implemented |
| `config/alerts.example.json` + docs | Implemented |

**Before merge:** run full `pytest`, manual `alerts test --dry-run` and live notification smoke (email and/or Slack), confirm tracker still evaluates alerts on a normal run. **No merge until validated.**

---

## What’s next (recommended order)

### 1. Finish & validate current alerts foundation (this branch)

- [ ] Full test suite passes locally and in CI
- [x] Manual smoke: live email delivery verified
- [ ] Manual smoke: Slack incoming webhook (optional)
- [ ] Tracker run with an enabled rule — confirm alert fires end-to-end
- [ ] Merge to `main` only after the above

### 2. **Alerts — Settings UI (next product milestone)** ← start immediately after §1 merges

Build a **dashboard Settings → Alerts** experience so users never touch raw JSON:

- [ ] List rules (read from `~/.market-helm/alerts.json` via new API)
- [ ] Enable/disable rules
- [ ] Add/edit: symbol, condition type, threshold (price alert v1)
- [ ] **Notification channels:** email address field, webhook URL (optional Slack toggle)
- [ ] **“Send test notification”** button (calls same path as CLI test)
- [ ] Save writes config through API (JSON remains storage v1; UI is the product surface)
- [ ] Clear empty state: “Add your email to get started” — not “copy this JSON file”

**Later (same epic):** user accounts, DB-backed subscriptions, SMS/push, always-on worker independent of manual “Fetch New”.

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

1. **Webhook notifier** — JSON POST to `webhook_url` or `ALERT_WEBHOOK_URL`.
2. **Projection accuracy** — API + Historical Trends UI.
3. **CI / release automation** — E2E smoke, post-release auto-finish (see [CHANGELOG.md](../CHANGELOG.md)).

*(SMTP email, Slack payloads, alerts CLI — pending validation on `feat/alerts-smtp-email`.)*

---

## Skipped / deferred / gaps — and how we address them

| Item | Why deferred | How we address it |
|------|----------------|-------------------|
| **Alert Settings UI** | Backend-first slice | **§2 above** — mandatory next milestone; JSON hidden behind API |
| **User accounts + DB** | Large scope | After Settings UI v1; store rules/contacts per user |
| **Always-on alert worker** | Tracker is batch/cron today | Scheduled job or hosted worker; decouple from “Fetch New” |
| **Phone / SMS / push** | Email first | After email UI works; Twilio/APNs/etc. |
| **Technical rules (RSI, AND/OR)** | Scope | [ALERTING_DESIGN.md](ALERTING_DESIGN.md); after basic subscribe UX |
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
