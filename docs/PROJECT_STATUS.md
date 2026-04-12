# Project status & roadmap

**Last updated:** 2026-04-11 — doc alignment with `main`; product vision, [DEPLOYMENT.md](DEPLOYMENT.md), hosting notes

This file is the **single place** for “where we are,” “what’s next,” and **gaps** (skipped or deferred work). Other READMEs link here for details.

---

## Product vision

**What we’re building toward** is a product—not only a CLI—that can:

1. **Monitor** the market on a schedule (screening, data fetch, summaries).
2. **Suggest** what to buy or sell (projections, recommendations, opportunities, alerts).
3. **Execute** trades on the user’s behalf **safely** (broker API, limits, audit trail)—**not in the codebase yet**; see [DEPLOYMENT.md](DEPLOYMENT.md).
4. **Serve more than one person** over time: the **CLI is already installable**; a hosted **app** with accounts would add auth, per-user data, and isolated secrets—likely a **database** instead of only shared files.

**Where we are today:** analysis + file-backed storage + dashboard + partial alerts (log + webhook). That’s the foundation; execution and multi-tenant SaaS are **later phases**, not a single jump.

**Disclaimer:** This is software design, not investment, legal, or tax advice. Automated trading has regulatory and broker rules; validate with professionals and your broker.

---

## Snapshot

| Area | Status | Notes |
|------|--------|--------|
| CLI / daily tracker | **Stable** | Core workflows, CSV/JSON output, tests for major modules |
| Web dashboard | **Active** | FastAPI + React; Historical Trends, projection accuracy, market views |
| Alerts | **Partial** | `AlertEngine`, `config/alerts.json`, **log** + **HTTP webhook** notifiers; no email/SNS/CLI UI yet |
| Historical / accuracy | **Partial** | Multi-day charts + **`GET /api/history/accuracy`** + UI on Historical Trends; limited “portfolio-level” metrics |
| Tests | **Good coverage** core + dashboard + alerts webhook; gaps in some `services/` modules |
| Hosting / deploy | **Documented** | See [DEPLOYMENT.md](DEPLOYMENT.md) — `DATA_DIR`, env vars, persistence; **no** automated execution in repo yet |

---

## Recently shipped (on `main`)

1. **Webhook notifier** (`src/alerts/notifiers/webhook_notifier.py`)  
   - JSON `POST` to `webhook_url` on the alert or `ALERT_WEBHOOK_URL`.  
   - Works with existing rules and cooldowns.

2. **Projection accuracy**  
   - Compares each run’s `target_mid` to the first available **close** on/after the target date (`projection_date` in CSV, else run date + 5 days).  
   - **`GET /api/history/accuracy?days=`** — summary, breakdown by recommendation, sample rows.  
   - **Historical Trends** page — KPIs, bar chart, recent scores table.

---

## What’s next (recommended order)

1. **Alerts — production-ready notifications**  
   - **SMTP / email** notifier (works everywhere).  
   - Optional: Slack/Discord **payload templates** (still via webhook).  
   - **Document** `config/alerts.example.json` and env vars in dashboard README.

2. **Alerts — operational UX**  
   - CLI: `market-helm alerts list|test` (even read-only first).  
   - Optional: minimal dashboard page to view/trigger test (read-only config).

3. **Projection accuracy — deeper analytics**  
   - Buckets by **confidence** band.  
   - Directional hit rate (price vs target) if we add run-day price to the scoring payload.  
   - **Business-day** target dates (align with market calendar) if we see weekend skew.

4. **Dashboard UX**  
   - Code splitting / lazy routes (bundle size warning).  
   - Watchlist, saved views (per CONTRIBUTING / dashboard README).

5. **Tests**  
   - `src/services/data_fetcher.py`, `stock_screener.py`, `index_fetcher.py` — add targeted tests.  
   - **Integration** test: tracker run with temp `data/` (optional, high value).

6. **Future: hosted execution (optional product direction)**  
   - Not implemented: **broker API** integration, **order** state in a **DB**, risk limits, paper-then-live.  
   - **Today:** deploy tracker + dashboard with persistent `DATA_DIR` per [DEPLOYMENT.md](DEPLOYMENT.md).  
   - **Before real money:** Postgres (or similar) for orders/audit; never store trading keys in git.

---

## Skipped / deferred / gaps — and how we address them

| Item | Why it was skipped / gap | How we address it |
|------|---------------------------|-------------------|
| **E2E browser tests** | Not in CI; manual only | Add Playwright/Cypress later or smoke script hitting `/health` + one API |
| **Email / SNS / Azure** | Webhook first (smallest slice) | Implement SMTP notifier using `smtplib` + env; cloud notifiers as separate PRs |
| **Slack block format** | Generic JSON is enough for v1 | Add `payload_format: slack` on alert → map event → Slack `blocks` in notifier |
| **Full alert product** (RSI, AND/OR, CLI) | Large scope | Keep [ALERTING_DESIGN.md](ALERTING_DESIGN.md); implement in vertical slices after email + CLI list |
| **Accuracy “confidence” metrics** | v1 focused on absolute % error by recommendation | Extend `compute_projection_accuracy` to join confidence from projection rows and aggregate |
| **CONTRIBUTING duplicate sections** | Doc drift | Removed in same docs PR; this file prevents future split-brain |
| **Real-time data** | Architecture is batch/daily | Documented as non-goal; optional WebSocket phase if needed |
| **Automated trading** | Out of scope for current codebase | New module + broker API + DB + compliance review; see [DEPLOYMENT.md](DEPLOYMENT.md) |

---

## How to keep this current

- After meaningful merges, update **Last updated**, **Recently shipped**, and **What’s next** in this file (or in the same PR as the feature).  
- Prefer **one** roadmap section in [CONTRIBUTING.md](../CONTRIBUTING.md) that points here for narrative detail.  
- Release notes: tag or PR description can copy from **Recently shipped**.

---

## Related docs

- [Deployment & persistence](DEPLOYMENT.md)  
- [Alerting design (full vision)](ALERTING_DESIGN.md)  
- [Dashboard design](DASHBOARD_DESIGN.md)  
- [Contributing](../CONTRIBUTING.md)  
- [Dashboard README](../dashboard/README.md)
