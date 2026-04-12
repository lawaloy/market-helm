# MarketHelm — web dashboard

Modern, interactive web dashboard for visualizing stock market data, projections, and recommendations.

## Install from PyPI (recommended)

After **`pip install market-helm`** (from the [main README](../README.md)), run:

```bash
market-helm-web
```

Then open **<http://localhost:8000>** — the API and the built React UI are served together. Data files are read from **`DATA_DIR`** if set, otherwise the repo’s **`data/`** folder when developing from a clone, or **`~/.market-helm/data`** when the package is installed from a wheel. On first run, if **`~/.market-helm`** does not exist but **`~/.market-desk`** does, it is **renamed** to **`~/.market-helm`** automatically.

Optional: **`HOST`**, **`PORT`**, **`CORS_ORIGINS`**, **`UVICORN_RELOAD`** — see [Environment Variables](#environment-variables) below.

---

## Development (clone + hot reload)

Use this when you are changing React/TypeScript and want Vite’s dev server.

### Prerequisites

- Python 3.12+
- Node.js 18+
- npm or yarn

### 1. Install the repo (editable) and frontend deps

From the repository root:

```bash
pip install -e .
cd dashboard/frontend && npm install
```

### 2. Start the backend

```bash
cd dashboard/backend
python main.py
```

Backend runs on **<http://localhost:8000>** (API only if you have not run `npm run build`; with a built `static/` bundle, `/` serves the SPA).

### 3. Start the Vite dev server (frontend)

```bash
cd dashboard/frontend
npm run dev
```

Vite defaults to **<http://localhost:3000>** and proxies `/api` to the backend.

### Rebuild the SPA for pip packaging

From `dashboard/frontend`:

```bash
npm run build
```

Output goes to **`dashboard/backend/static/`** (not committed; release wheels are built in CI with `npm run build` before packaging). For a local wheel/sdist, run this step before **`python -m build`**.

### 4. Open the app (dev)

Navigate to **<http://localhost:3000>** in your browser (Vite dev server).

## Features

### Phase 1 MVP (Implemented)

✅ **Dashboard Overview**

- Market overview with KPI cards
- Top gainers/losers chart
- Recommendation distribution pie chart
- STRONG BUY opportunities section
- Filterable/sortable stock table
- Stock detail modal

### Historical Trends (implemented)

The **Historical Trends** page is shipped. It includes:

- Multi-day market summary charts (confidence, expected move, recommendations over time)
- **Single-stock** view: price vs 5-day target over your selected range
- **Projection accuracy**: compares older projections’ target prices to the **actual closing price** on or after each projection’s target date; shows rollups by recommendation and a table of recent scores

**Why “projection accuracy” can look empty:**  
Nothing is wrong with the UI. The accuracy block only has numbers to show when **both** are true: (1) you have saved runs in the `data/` folder across multiple dates (`daily_data_*.csv` and `projections_*.csv`), and (2) enough **calendar time has passed** that each projection’s **target date** is in the past, so there is a real close to compare. Until then you may still see the market charts, while accuracy stays in its empty state. Keep running **Fetch New** on successive days (or add historical files) and it will fill in over time.

### Phase 2 (still in progress)

Other dashboard Phase 2 ideas (watchlist, code splitting, keyboard shortcuts, etc.) are **not** finished yet. See **What’s Next?** below and [docs/PROJECT_STATUS.md](../docs/PROJECT_STATUS.md).

### API Endpoints

- `/api/market/overview` - Market statistics
- `/api/market/movers` - Top gainers/losers
- `/api/summary` - Market summary (Expert or Learner)
- `/api/projections/summary` - Projections overview
- `/api/projections/opportunities` - Buy/Sell opportunities
- `/api/stocks/{symbol}` - Stock details
- `/api/stocks/{symbol}/historical` - Historical data
- `/api/history/summary` - Aggregated historical summary over time
- `/api/history/accuracy` - Projection vs actual accuracy (see [docs/PROJECT_STATUS.md](../docs/PROJECT_STATUS.md))

### Technologies

- FastAPI backend with pandas data loading
- React 18 + TypeScript frontend
- TailwindCSS for styling
- Recharts for visualizations
- Headless UI for modals

## Project Structure

```text
dashboard/
├── backend/              # FastAPI Backend
│   ├── main.py          # Entry point
│   ├── api/             # API endpoints
│   ├── models/          # Pydantic models
│   └── services/        # Data loading services
│
└── frontend/            # React Frontend
    ├── src/
    │   ├── components/  # React components
    │   ├── pages/       # Page components
    │   ├── services/    # API client
    │   ├── types/       # TypeScript types
    │   └── utils/       # Utilities
    └── package.json
```

## API Documentation

With the backend running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Backend Development

```bash
cd dashboard/backend
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd dashboard/frontend
npm run dev
```

### Build for Production

**Backend:**

```bash
cd dashboard/backend
# Use the Dockerfile in the root or deploy to Railway/Render/Fly.io
```

**Frontend:**

```bash
cd dashboard/frontend
npm run build
# Deploy to Vercel/Netlify
```

## Environment Variables

**Backend:**

- `DATA_DIR` - Path to data directory (defaults to `../../data`). In production, set to a **persistent** absolute path (see [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)).
- `CORS_ORIGINS` - Allowed CORS origins (defaults to localhost:3000)

**Alerts (Python tracker / `config/alerts.json`):**

- `ALERT_WEBHOOK_URL` - Default webhook URL if an alert uses `"notifications": ["webhook"]` without per-rule `webhook_url` (see [docs/PROJECT_STATUS.md](../docs/PROJECT_STATUS.md))

**Frontend:**

- `VITE_API_URL` - Backend API URL (defaults to `http://localhost:8000`)

## Troubleshooting

### Backend Issues

#### "No data files found"

- Make sure you've run **`market-helm`** (or `python main.py`) at least once to generate data files
- Check that the `data/` directory exists in the project root

#### CORS errors

- Backend allows localhost:3000 by default
- For production, update CORS settings in `backend/main.py`

### Frontend Issues

#### "Failed to fetch"

- Make sure the backend is running on port 8000
- Check browser console for specific errors

#### Components not styling correctly

- Run `npm install` to ensure all dependencies are installed
- TailwindCSS requires PostCSS - check that postcss.config.js exists

## What's Next?

**Status:** See [docs/PROJECT_STATUS.md](../docs/PROJECT_STATUS.md) for repo-wide roadmap, skipped items, and how we plan to close gaps.

**Dashboard-focused next steps:**

1. **Performance** — Code splitting, lazy route loading (bundle size)
2. **Watchlist** — Save favorite symbols (local persistence first)
3. **Keyboard shortcuts** — Quick navigation
4. **Alerts (future)** — Optional UI to view/test rules (backend alerts today live in `config/alerts.json` + **webhook** / log)

See [DASHBOARD_DESIGN.md](../docs/DASHBOARD_DESIGN.md) for full Phase 2 design.

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

MIT License - See [LICENSE](../../LICENSE)
