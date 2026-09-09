# MarketHelm web dashboard development

This guide is only for developing or rebuilding the React/FastAPI dashboard.
For installing and running MarketHelm, start with the
[main README](../README.md). For hosted configuration, persistence, and secrets,
use the [deployment guide](../docs/DEPLOYMENT.md).

## Web architecture

- `dashboard/frontend/` contains the React and TypeScript application.
- `dashboard/backend/` contains the FastAPI application and API routes.
- During development, Vite serves the UI on port 3000 and proxies `/api` to
  FastAPI on port 8000.
- A production build is written to `dashboard/backend/static/`. FastAPI then
  serves the compiled UI and API together on port 8000.

The frontend is therefore part of the web application image; it is not normally
deployed as an independent Vercel or Netlify application.

## Development with hot reload

### Requirements

- Python 3.12 or newer
- The Node.js version in [`.nvmrc`](../.nvmrc)
- npm

From the repository root, install the Python package and frontend dependencies:

```bash
pip install -e .
cd dashboard/frontend
npm ci
cd ../..
```

Start FastAPI from the repository root:

```bash
python3 -m uvicorn dashboard.backend.main:app --reload --port 8000
```

In another terminal, start Vite:

```bash
cd dashboard/frontend
npm run dev
```

Open <http://localhost:3000>. The API documentation remains available at
<http://localhost:8000/docs>.

If port 3000 is occupied, use the repository's paired alternate ports. Start
FastAPI with `python3 -m uvicorn dashboard.backend.main:app --reload --port 8001`,
then run `npm run dev:3001` in `dashboard/frontend/` and open
<http://localhost:3001>.

On Windows PowerShell, replace `python3` in this guide with
`.\.venv\Scripts\python.exe`.

## Build the integrated web application

Build the React UI:

```bash
cd dashboard/frontend
npm run build
```

The output goes to `dashboard/backend/static/`. Return to the repository root
and start the integrated application:

```bash
market-helm-web
```

Open <http://localhost:8000>. Release automation performs the same frontend
build before creating the Python package, and [`Dockerfile.web`](../Dockerfile.web)
performs it in a Node build stage before constructing the Python runtime image.

## Verification

Run frontend checks from `dashboard/frontend/`:

```bash
npm test
npm run build
```

Run backend tests from the repository root:

```bash
python3 -m pytest tests/dashboard/ -v
```

The complete required checks and development workflow are documented in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Configuration and behavior

- `DATA_DIR` selects the market-data directory. A source checkout defaults to
  the repository's `data/`; an installed wheel defaults to the user data directory.
- `HOST`, `PORT`, and `UVICORN_RELOAD` control `market-helm-web`.
- `CORS_ORIGINS` configures allowed browser origins.
- `VITE_DEV_PORT` and `VITE_DEV_API_TARGET` affect only the Vite development server.
- Database, authentication, email, proxy, rate-limit, and alert-worker variables
  are documented only in [Deployment and persistence](../docs/DEPLOYMENT.md).

Feature availability and unfinished work are tracked only in
[Project status](../docs/PROJECT_STATUS.md). API groups and service boundaries
are documented in [Architecture](../docs/ARCHITECTURE.md#webapi-boundaries).
