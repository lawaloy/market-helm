# AGENTS.md

## Cursor Cloud specific instructions

### Overview

MarketHelm is a stock market monitoring CLI + web dashboard. The repo has two main components:

- **Python backend** (FastAPI, CLI): root `src/`, `dashboard/backend/`, `main.py`
- **React/TypeScript frontend**: `dashboard/frontend/`

No database is required — data is flat-file (CSV/JSON in `data/`).

### Running services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| FastAPI backend | `python3 dashboard/backend/main.py` | 8000 | Serves API + built SPA from `dashboard/backend/static/` |
| Vite dev server | `cd dashboard/frontend && npm run dev` | 3000 | Proxies `/api` to backend; use for frontend hot-reload |

Start the backend **before** the Vite dev server. Use `python3` (not `python`) — the system does not have a `python` symlink.

### Lint, test, build

See CI in `.github/workflows/python-app.yml` and `.github/workflows/pr-e2e.yml`.

- **Lint**: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- **Tests**: `pytest tests/ -v` (110 tests, all pure unit/integration — no API key needed)
- **Frontend build**: `cd dashboard/frontend && npm run build` (outputs to `dashboard/backend/static/`)

### Opening pull requests

When creating PRs (including via `gh pr create`), use [`.github/pull_request_template.md`](.github/pull_request_template.md):

- **`## What + Why`** with at least one filled bullet (not `## Summary`)
- **`## Checks`** for local verification before push
- **`<!-- AUTO:START -->` … `<!-- AUTO:END -->`** markers so the PR Description workflow can update the file list in place

```bash
gh pr create --title "..." --body-file .github/pull_request_template.md
```

Fill in **What + Why** before the next push. Details: [CONTRIBUTING.md](CONTRIBUTING.md#6-push-and-create-pull-request).

### Gotchas

- `flake8` and `pytest` are installed to `~/.local/bin` — make sure `PATH` includes it (`export PATH="$HOME/.local/bin:$PATH"`).
- The `FINNHUB_API_KEY` env var is required only for live data fetching (CLI `market-helm` or dashboard "Fetch New" button). All tests mock the API and run without it.
- The `OPENAI_API_KEY` is fully optional; without it, AI summaries fall back to template-based demo text.
- Dashboard API endpoints (e.g. `/api/market/overview`) return 404 `"No data available."` or 500 when no data files exist in `data/` — this is expected on a fresh clone before the first fetch.
- The frontend build outputs to `dashboard/backend/static/`; FastAPI serves this as a SPA mount if the directory exists.
- The Vite dev server proxies `/api` requests to the backend on port 8000. When developing frontend, use `http://localhost:3000`; when testing the built SPA, use `http://localhost:8000`.
- Clicking "Fetch New" in the dashboard UI triggers a live data fetch via the Finnhub API and will fail gracefully without `FINNHUB_API_KEY`, showing an error banner in the UI.
