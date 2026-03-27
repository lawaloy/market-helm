# Stock Exchange Tracker Dashboard

Modern, interactive web dashboard for visualizing stock market data, projections, and recommendations.

**Not on PyPI:** The CLI is installable with `pip install stock-exchange-tracker`; the dashboard is **not** part of that wheel. You need this repository (or a copy of `dashboard/`), **Python 3.12+**, and **Node.js 18+** to run backend + frontend—see Quick Start below.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- npm or yarn

### 1. Start the Backend

```bash
cd dashboard/backend

# Create virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate
# Or Mac/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
```

Backend will run on `http://localhost:8000`

### 2. Start the Frontend

```bash
cd dashboard/frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

Frontend will run on `http://localhost:3000`

### 3. Open the Dashboard

Navigate to `http://localhost:3000` in your browser.

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

- Make sure you've run the stock tracker at least once to generate data files
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
