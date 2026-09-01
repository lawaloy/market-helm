# AGENTS.md

## Cursor Cloud specific instructions

### Overview

MarketHelm is a stock market monitoring CLI + web dashboard. The repo has two main components:

- **Python backend** (FastAPI, CLI): root `src/`, `dashboard/backend/`, `main.py`
- **React/TypeScript frontend**: `dashboard/frontend/`

No database is required — data is flat-file (CSV/JSON in `data/`).

### Running services

| Service         | Command                                | Port | Notes                                                   |
| --------------- | -------------------------------------- | ---- | ------------------------------------------------------- |
| FastAPI backend | `python3 dashboard/backend/main.py`    | 8000 | Serves API + built SPA from `dashboard/backend/static/` |
| Vite dev server | `cd dashboard/frontend && npm run dev` | 3000 | Proxies `/api` to backend; use for frontend hot-reload  |

Start the backend **before** the Vite dev server. Use `python3` (not `python`) — the system does not have a `python` symlink.

### Lint, test, build

See CI in `.github/workflows/python-app.yml` and `.github/workflows/pr-e2e.yml`.

- **Lint**: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- **Tests**: `pytest tests/ -v --ignore=tests/integration/test_postgresql_storage.py` (database-free suite; no API key needed)
- **PostgreSQL integration**: set `MARKET_HELM_POSTGRES_TEST_URL`, then run `pytest tests/integration/test_postgresql_storage.py -v`
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

For ordinary PRs, do not enable auto-merge when creating the PR. Wait until all workflows and check integrations expected for the PR’s event and changed paths have produced runs for the latest head commit and every resulting run is terminal, including checks not required by branch protection. Also wait for any PR review automation still running against an earlier commit, because it may post relevant feedback after a push. If an expected run does not appear, investigate the missing run rather than treating its absence as success. Success is acceptable; accept a skipped or neutral conclusion only when it is expected and documented. Failure, cancellation, timeout, or action-required conclusions block completion.
Then inspect the PR conversation, submitted reviews, and inline review threads. Address every actionable item, reply with the outcome, and resolve a thread only after the concern is fixed or answered with documented rationale.
Repeat the complete wait-and-inspect cycle after every push because a new head commit invalidates the previous check and review assessment. Immediately before completion, re-check the latest commit, all check and review-automation runs, and all three feedback surfaces. Merge manually only when nothing is pending, no expected runs are missing, no unacceptable conclusions remain, and no actionable feedback is unresolved.

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
