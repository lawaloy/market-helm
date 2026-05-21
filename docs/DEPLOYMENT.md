# Deployment & persistence

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
| `ALERT_WEBHOOK_URL` | Tracker (alerts) | Default webhook when rules use `webhook` without per-rule `url` |
| `ALERT_WEBHOOK_FORMAT` | Tracker (alerts) | `json`, `slack`, or `discord` webhook body format |
| `DISCORD_WEBHOOK_URL` | Tracker (alerts) | Default Discord incoming webhook URL when a rule has no `webhook_url` |
| `MARKET_HELM_ALERTS_CONFIG` | Tracker (alerts) | Optional path to `alerts.json` (default `~/.market-helm/alerts.json`) |
| `SMTP_HOST` | Tracker (alerts) | SMTP server for `email` notifications |
| `SMTP_PORT` | Tracker (alerts) | SMTP port (default `587`) |
| `SMTP_USER` | Tracker (alerts) | SMTP username |
| `SMTP_PASSWORD` | Tracker (alerts) | SMTP password or app password |
| `ALERT_EMAIL_TO` | Tracker (alerts) | Default recipients for `email` notifications |
| `ALERT_EMAIL_FROM` | Tracker (alerts) | Optional From header (defaults to `SMTP_USER`) |

**Dev vs product email:** these variables are for **self-host / operator** SMTP (e.g. personal Gmail). Hosted product delivery (platform `From`, user `To` in Settings) is described in [PROJECT_STATUS.md — Production alert delivery (target)](PROJECT_STATUS.md#production-alert-delivery-target). Provider runbooks (SendGrid, SES, etc.) go in DEPLOYMENT when implemented.

Never commit values; use your host’s secret manager or encrypted env.

---

## Typical deployment layout

1. **Backend** — Run FastAPI (`uvicorn` or `python main.py`) with `DATA_DIR` and `FINNHUB_API_KEY` set.
2. **Frontend** — Build `dashboard/frontend` (`npm run build`) and serve `dist/` from a static host (or the same reverse proxy).
3. **Scheduler** — Run the daily tracker on a schedule (cron, GitHub Actions with self-hosted runner, or the platform’s scheduler) **or** use the dashboard “Fetch New” flow if you only trigger manually.

**CORS:** set `CORS_ORIGINS` to your frontend origin so the browser can call the API.

---

## Future: hosting and **automated trading** (not implemented yet)

This repo today is **analysis + dashboard + alerts**. It does **not** place orders. The **product direction** (monitor → suggest → execute, multi-user) is in [PROJECT_STATUS.md](PROJECT_STATUS.md#product-vision). If you later add **automated buy/sell**:

1. **Broker API** — You need a broker that exposes **order placement** (e.g. Alpaca, Interactive Brokers, Tradier). Finnhub is **market data**, not a substitute for execution.
2. **Secrets** — Trading keys must live only in **host secrets**; rotate and scope to paper vs live.
3. **Persistence** — Use a **database** (e.g. PostgreSQL) for orders, positions, and audit logs—**before** trusting real money.
4. **Safety** — Paper trading first, hard limits (max position, max loss), kill switch, full logging.

This is **not legal or financial advice**; follow your broker’s terms and applicable regulations.

---

## Related

- [PROJECT_STATUS.md](PROJECT_STATUS.md) — roadmap and future execution notes  
- [Dashboard README](../dashboard/README.md) — local dev, env vars  
- [Contributing](../CONTRIBUTING.md) — development workflow
