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

Open PRs **ready for review by default**. Use `--draft` only when the user explicitly requests a draft or the work is intentionally incomplete.

For GitHub-side operations, use the installed **GitHub app/connector** whenever its
tools are available. This includes creating or updating PRs, enabling auto-merge,
checking workflow/status results, merging, and reading PR metadata. Do **not**
default to GitHub CLI authentication. Use `gh` only as an explicitly disclosed
fallback when the connector is unavailable or lacks the required operation.

Continue to use local `git` for working-tree operations such as branches, commits,
fetch, push, checkout, and pull; the connector does not synchronize the local
working tree.

Before merging or declaring a PR complete, inspect its conversation comments,
submitted reviews, and inline review threads. Address every actionable item,
reply with the outcome, and resolve the thread only after the concern is fixed
or answered with a documented rationale. Re-check all three surfaces after each
push and immediately before completion because feedback can arrive while CI is
running.

When creating PRs, use [`.github/pull_request_template.md`](.github/pull_request_template.md):

- **`## What + Why`** with at least one filled bullet (not `## Summary`)
- **`## Checks`** for local verification before push
- **`<!-- AUTO:START -->` … `<!-- AUTO:END -->`** markers so the PR Description workflow can update the file list in place

Fill in **What + Why** before the next push. Details: [CONTRIBUTING.md](CONTRIBUTING.md#6-push-and-create-pull-request).

### Gotchas

- `flake8` and `pytest` are installed to `~/.local/bin` — make sure `PATH` includes it (`export PATH="$HOME/.local/bin:$PATH"`).
- The `FINNHUB_API_KEY` env var is required only for live data fetching (CLI `market-helm` or dashboard "Fetch New" button). All tests mock the API and run without it.
- The `OPENAI_API_KEY` is fully optional; without it, AI summaries fall back to template-based demo text.
- Dashboard API endpoints (e.g. `/api/market/overview`) return 404 `"No data available."` or 500 when no data files exist in `data/` — this is expected on a fresh clone before the first fetch.
- The frontend build outputs to `dashboard/backend/static/`; FastAPI serves this as a SPA mount if the directory exists.
- The Vite dev server proxies `/api` requests to the backend on port 8000. When developing frontend, use `http://localhost:3000`; when testing the built SPA, use `http://localhost:8000`.
- Clicking "Fetch New" in the dashboard UI triggers a live data fetch via the Finnhub API and will fail gracefully without `FINNHUB_API_KEY`, showing an error banner in the UI.
