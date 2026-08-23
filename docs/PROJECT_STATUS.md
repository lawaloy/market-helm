# Project status and roadmap

**Last updated:** 2026-08-22

This is the authoritative inventory of what MarketHelm currently ships, what is
covered by automated tests, and what remains unfinished. Deployment instructions
live in [DEPLOYMENT.md](DEPLOYMENT.md); design documents describe longer-term ideas
and should not be read as implementation claims.

## Product direction

MarketHelm is a stock-market monitoring product with a Python CLI and a React web
dashboard. It screens and fetches market data, produces heuristic short-term
projections, stores historical runs, and can notify users when alert rules match.

The repository supports two operating modes:

- **Local/self-hosted mode:** market data and alert preferences are flat files.
- **Hosted multi-user mode:** market data remains shared flat-file data, while
  accounts, sessions, per-user alert settings, jobs, and delivery history use
  SQLite or PostgreSQL.

Automated broker execution is a future direction, not a current capability.
MarketHelm does not provide investment, legal, or tax advice.

## Status definitions

| Label | Meaning |
|-------|---------|
| **Shipped and tested** | Implemented with automated coverage in this repository |
| **Shipped; operational verification needed** | Implemented and tested in isolation, but requires a real provider or hosted environment to validate end to end |
| **Partial** | A useful first version exists, with material scope still open |
| **Not implemented** | Design or roadmap only |

Automated coverage does not mean every production integration has been exercised.
For example, tests mock Finnhub and notification providers; managed PostgreSQL,
real email delivery, DNS, TLS, backups, and restore procedures require staging.

## Current capability matrix

| Area | Status | What exists | Important remaining work |
|------|--------|-------------|--------------------------|
| CLI and daily tracker | **Shipped and tested** | Index screening, quote/profile fetch, analysis, projections, CSV/JSON/Markdown output | Live Finnhub smoke testing and broader service-level failure tests |
| Web dashboard | **Shipped and tested** | Overview, movers, stock detail, summaries, historical trends, accuracy, refresh controls, exports, dark mode | Route-level code splitting, saved views/watchlists, keyboard shortcuts, performance/accessibility passes |
| Projection model | **Partial** | Five-day heuristic targets, confidence, risk, and recommendations | Backtesting, calibration, business-day targets, confidence-band analytics, fundamentals/news/ML |
| Historical accuracy | **Partial** | API and UI compare past projections with later closes | Richer metrics, confidence cohorts, risk-adjusted views, clearer market-calendar handling |
| Alerts | **Shipped and tested** | Price and screening rules, cooldowns, log/webhook/email delivery, retries, scheduled worker, delivery history, Helmtower UI | Technical-indicator and compound rules; SMS/push; real-provider staging tests |
| Accounts and tenant isolation | **Shipped and tested** | Registration, login/logout, bearer sessions, email verification, password reset/change, account deletion, per-user alert data | Account export and stronger administrative/support tooling |
| Hosted persistence | **Shipped; operational verification needed** | SQLite/PostgreSQL adapter, versioned migrations, PostgreSQL integration gate, queue/orchestrator | Managed staging, connection pooling validation, backup/restore drills, failover planning |
| Production controls | **Shipped; operational verification needed** | API rate limiting, trusted-proxy handling, liveness/readiness/worker health, metrics | Production dashboards/alerts, capacity testing, retention policy, operational runbooks |
| Automated trading | **Not implemented** | No broker connection or order execution | Broker integration, order/risk model, audit trail, compliance and safety controls |

## Hosted alerts and accounts

The hosted foundation is implemented. When `MARKET_HELM_DATABASE_URL` is set,
alert routes require authentication and scope configuration, watches, jobs, and
delivery history to the signed-in user. The account lifecycle includes:

- registration, login, current-user lookup, and logout;
- optional email-verification enforcement;
- verification and password-reset email flows;
- password change with session invalidation; and
- account deletion.

The database-backed worker evaluates enabled watches across users and records
per-channel outcomes. SMTP, SendGrid, and Mailgun are supported for platform email;
generic, Slack, and Discord webhook formats are supported. Retry/backoff is
configurable with `ALERT_DELIVERY_*` environment variables.

Local mode remains intentionally supported. Without `MARKET_HELM_DATABASE_URL`,
Helmtower and the alert CLI use the operator's `alerts.json` file and environment
credentials. End users of a hosted deployment do not provide SMTP credentials.

See [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries and
[DEPLOYMENT.md](DEPLOYMENT.md) for hosted configuration.

## Test posture and known verification gaps

The repository has broad Python and frontend unit/integration coverage, including
auth lifecycle, tenant isolation, storage migrations, worker orchestration,
delivery history, rate limits, security boundaries, API routes, and UI flows. CI
also defines a PostgreSQL 16 integration gate and browser smoke coverage.

The following should not be inferred from those tests:

- live Finnhub availability, quota behavior, or full-market run reliability;
- successful delivery through production SendGrid, Mailgun, SMTP, Slack, or Discord;
- managed PostgreSQL backup, restore, failover, pooling, and TLS behavior;
- production ingress/proxy correctness and sustained-load capacity;
- complete cross-browser, mobile-device, accessibility, and performance coverage; or
- financial validity of the projection heuristic.

These are the highest-value testing gaps because they cross system boundaries that
unit tests and container-only integration tests cannot fully reproduce.

## Recommended next work

1. **Hosted staging:** deploy the API, worker, PostgreSQL, and one transactional
   email provider; validate migrations, email links, proxy headers, metrics, and
   tenant isolation end to end.
2. **Operational safety:** rehearse backup/restore, define retention and incident
   runbooks, add capacity/load tests, and connect health/metrics to monitoring.
3. **Projection validation:** add repeatable backtests, confidence calibration,
   confidence-band reports, and explicit market-calendar semantics.
4. **Alert depth:** add technical-indicator and compound conditions; consider
   SMS/push only after hosted email is proven reliable.
5. **Dashboard quality:** code-split routes, run accessibility/performance audits,
   and decide whether saved watchlists/views belong in the product.
6. **Service integration coverage:** add controlled tests around fetcher errors,
   provider throttling, malformed upstream data, and a complete tracker run.

## Explicitly deferred

| Item | Reason |
|------|--------|
| Automated trading | Requires a separate risk, compliance, broker, and audit design |
| SMS and push notifications | Email/webhook production operation should be proven first |
| Advanced technical/compound alert rules | Current price and screening rules cover the initial alert product |
| International exchanges | Current screening is centered on S&P 500 and NASDAQ-100 |
| ML/fundamental/news projections | Current projection engine is intentionally heuristic |

## Keeping this document current

- Update the date and capability matrix after meaningful behavior changes.
- Distinguish code completion from real-environment operational verification.
- Link roadmap references here instead of maintaining conflicting status lists.
- Keep release-specific history in [CHANGELOG.md](../CHANGELOG.md).

## Related documentation

- [Deployment and persistence](DEPLOYMENT.md)
- [Dashboard guide](../dashboard/README.md)
- [Architecture](ARCHITECTURE.md)
- [Contributing](../CONTRIBUTING.md)
