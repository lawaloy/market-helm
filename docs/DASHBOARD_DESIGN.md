# Web Dashboard Design (spec — largely implemented)

## Overview

A modern, responsive web dashboard for visualizing stock market data, projections, and recommendations in real-time. Transforms CSV/JSON data into interactive, actionable insights.

## Priority: CRITICAL (original plan)

**Status:** **Shipped on `main`** — FastAPI + React dashboard, including Historical Trends and projection accuracy (`GET /api/history/accuracy`). Operational docs: [dashboard/README.md](../dashboard/README.md), roadmap: [PROJECT_STATUS.md](PROJECT_STATUS.md).

**This file** is the detailed **design spec** (API shapes, UX wireframes, phased ideas). Where it disagrees with the repo, trust the READMEs and `PROJECT_STATUS.md`.

**Estimated Effort (historical):** MVP was on the order of 1–2 weeks.

**Impact:** Very High - Makes data accessible and actionable

**Dependencies:** None (reads existing CSV/JSON output)

---

## Use Cases

### 1. Daily Market Monitoring

```text
User opens dashboard at 9 AM
→ Sees market overview with 196 tracked stocks
→ Identifies 11 STRONG BUY opportunities
→ Clicks on APP stock to see detailed projection
→ Views confidence score (90%) and risk level (Low)
→ Makes informed buying decision
```

### 2. Portfolio Research

```text
User searches for specific stocks (e.g., "AAPL")
→ Views historical price trends
→ Sees how recommendations changed over time
→ Compares actual vs projected prices
→ Assesses projection accuracy
```

### 3. Market Sentiment Analysis

```text
User views sentiment distribution
→ 67.8% HOLD, 22.6% BUY, 9.6% SELL
→ Market is mostly neutral with bullish bias
→ Identifies sector trends
→ Spots emerging opportunities
```

---

## Architecture

### Tech Stack

**Frontend:**

- **Framework:** React 18+ with TypeScript
- **Styling:** TailwindCSS + Headless UI
- **Charts:** Recharts or Chart.js
- **State Management:** React Context API (or Zustand for larger state)
- **Data Fetching:** SWR or TanStack Query (React Query)
- **Icons:** Heroicons or Lucide React
- **Routing:** React Router v6

**Backend:**

- **Framework:** FastAPI (Python 3.12+)
- **Data Loading:** Pandas for CSV/JSON processing
- **WebSocket:** For real-time updates (optional Phase 2)
- **API Documentation:** Auto-generated with FastAPI (Swagger/OpenAPI)
- **CORS:** Enabled for local development

**Deployment:**

- **Frontend:** Vercel, Netlify, or GitHub Pages
- **Backend:** Railway, Render, or Fly.io
- **Database:** SQLite (for historical data caching - Phase 2)
- **File Storage:** Local filesystem (reads from `data/` folder)

### Project Structure

```text
market-helm/
├── dashboard/                      # NEW: Web Dashboard
│   ├── backend/                    # FastAPI Backend
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── market.py           # Market overview endpoints
│   │   │   ├── projections.py      # Projection endpoints
│   │   │   ├── stocks.py           # Individual stock endpoints
│   │   │   └── historical.py       # Historical data endpoints
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── market.py           # Pydantic models
│   │   │   ├── projection.py
│   │   │   └── stock.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── data_loader.py      # Load CSV/JSON from data/
│   │   │   ├── cache.py            # Optional caching layer
│   │   │   └── aggregation.py      # Data aggregation logic
│   │   └── requirements.txt
│   │
│   └── frontend/                   # React Frontend
│       ├── public/
│       │   ├── index.html
│       │   └── favicon.ico
│       ├── src/
│       │   ├── components/
│       │   │   ├── layout/
│       │   │   │   ├── Header.tsx
│       │   │   │   ├── Sidebar.tsx
│       │   │   │   └── Footer.tsx
│       │   │   ├── cards/
│       │   │   │   ├── KPICard.tsx
│       │   │   │   ├── StockCard.tsx
│       │   │   │   └── OpportunityCard.tsx
│       │   │   ├── charts/
│       │   │   │   ├── MarketOverviewChart.tsx
│       │   │   │   ├── GainersLosersChart.tsx
│       │   │   │   ├── SentimentPieChart.tsx
│       │   │   │   └── HistoricalTrendChart.tsx
│       │   │   ├── tables/
│       │   │   │   ├── StockTable.tsx
│       │   │   │   ├── ProjectionTable.tsx
│       │   │   │   └── FilterBar.tsx
│       │   │   └── modals/
│       │   │       ├── StockDetailModal.tsx
│       │   │       └── CompareModal.tsx
│       │   ├── pages/
│       │   │   ├── Dashboard.tsx       # Main dashboard
│       │   │   ├── Projections.tsx     # Projections view
│       │   │   ├── Historical.tsx      # Historical trends
│       │   │   ├── StockDetail.tsx     # Individual stock
│       │   │   └── Settings.tsx        # User settings
│       │   ├── hooks/
│       │   │   ├── useMarketData.ts
│       │   │   ├── useProjections.ts
│       │   │   └── useStockDetail.ts
│       │   ├── services/
│       │   │   └── api.ts              # API client
│       │   ├── types/
│       │   │   └── index.ts            # TypeScript types
│       │   ├── utils/
│       │   │   ├── formatters.ts       # Number/date formatting
│       │   │   └── calculations.ts     # Client-side calcs
│       │   ├── App.tsx
│       │   ├── index.tsx
│       │   └── index.css
│       ├── package.json
│       ├── tsconfig.json
│       └── tailwind.config.js
│
├── data/                           # Existing data folder
│   ├── daily_data_*.csv
│   ├── projections_*.csv
│   └── summary_*.json
└── ...
```

---

## API Endpoints

### Market Overview

```http
GET /api/market/overview
```

**Response:**

```json
{
  "date": "2026-01-11",
  "totalStocks": 196,
  "gainers": 115,
  "losers": 80,
  "unchanged": 1,
  "averageChange": 0.72,
  "maxChange": 12.01,
  "minChange": -5.77,
  "indices": {
    "SP500": {
      "stocks": 98,
      "avgChange": 0.62,
      "gainers": 55,
      "losers": 42
    },
    "NASDAQ100": {
      "stocks": 98,
      "avgChange": 0.83,
      "gainers": 60,
      "losers": 38
    }
  }
}
```

### Projections Summary

```http
GET /api/projections/summary
```

**Response:**

```json
{
  "date": "2026-01-11",
  "targetDate": "2026-01-16",
  "totalProjections": 177,
  "averageConfidence": 70.7,
  "expectedMarketMove": 0.23,
  "sentiment": "Neutral",
  "recommendations": {
    "STRONG_BUY": 11,
    "BUY": 29,
    "HOLD": 120,
    "SELL": 15,
    "STRONG_SELL": 2
  },
  "trends": {
    "Bullish": 31,
    "Neutral": 135,
    "Bearish": 11
  },
  "riskProfile": {
    "Low": 169,
    "Medium": 7,
    "High": 1
  }
}
```

### Top Opportunities

```http
GET /api/projections/opportunities?type=STRONG_BUY&limit=10
```

**Query Parameters:**

- `type`: STRONG_BUY | BUY | SELL | STRONG_SELL
- `limit`: Number of results (default: 10)

**Response:**

```json
{
  "type": "STRONG_BUY",
  "count": 11,
  "opportunities": [
    {
      "symbol": "APP",
      "name": "AppLovin Corp",
      "currentPrice": 647.72,
      "targetPrice": 655.91,
      "expectedChange": 1.3,
      "confidence": 90,
      "risk": "Low",
      "trend": "Bullish",
      "reason": "Strong +5.1% gain; very strong momentum; low volume caution",
      "volume": 2500000,
      "momentum": 85.2,
      "volatility": 12.3
    }
  ]
}
```

### Stock Details

```http
GET /api/stocks/{symbol}
```

**Response:**

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc",
  "currentData": {
    "price": 259.37,
    "change": 0.33,
    "changePercent": 0.13,
    "volume": 45000000,
    "marketCap": 3500000000000
  },
  "projection": {
    "targetDate": "2026-01-16",
    "targetPrice": 262.50,
    "expectedChange": 1.2,
    "confidence": 75,
    "recommendation": "BUY",
    "risk": "Low",
    "trend": "Bullish"
  },
  "technical": {
    "momentum": 65.5,
    "volatility": 15.2,
    "rsi": 58.3
  }
}
```

### Historical Data

```http
GET /api/stocks/{symbol}/historical?days=30
```

**Query Parameters:**

- `days`: Number of days (default: 30, max: 365)

**Response:**

```json
{
  "symbol": "AAPL",
  "data": [
    {
      "date": "2026-01-11",
      "close": 259.37,
      "change": 0.13,
      "volume": 45000000,
      "projection": {
        "targetPrice": 262.50,
        "confidence": 75,
        "recommendation": "BUY"
      }
    }
  ]
}
```

### Top Gainers/Losers

```http
GET /api/market/movers?type=gainers&limit=10
GET /api/market/movers?type=losers&limit=10
```

**Response:**

```json
{
  "type": "gainers",
  "data": [
    {
      "symbol": "BLDR",
      "name": "Builders FirstSource Inc",
      "price": 124.66,
      "change": 12.01,
      "volume": 3200000
    }
  ]
}
```

---

## User Interface Design

### Page 1: Dashboard (Home)

**Layout:**

```text
┌─────────────────────────────────────────────────────────────────┐
│ 📊 MarketHelm    [Dashboard] [Projections] [⚙️]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│ │ 196      │ │ 70.7%    │ │ +0.23%   │ │ 11       │           │
│ │ Stocks   │ │ Avg Conf │ │ Expected │ │ Strong   │           │
│ │ Tracked  │ │          │ │ Move     │ │ Buys     │           │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                  │
│ ┌────────────────────────────┐ ┌────────────────────────────┐ │
│ │ Top 10 Movers              │ │ Recommendation Distribution │ │
│ │ ═════════════ +12.0% BLDR  │ │                             │ │
│ │ ═══════════ +10.8% INTC    │ │   [Pie Chart]               │ │
│ │ ═══════ +8.7% LRCX         │ │   67.8% HOLD                │ │
│ │ ...                        │ │   22.6% BUY                 │ │
│ │ ══ -5.8% MSTR              │ │   9.6% SELL                 │ │
│ └────────────────────────────┘ └────────────────────────────┘ │
│                                                                  │
│ STRONG BUY Opportunities (11)          [View All →]          │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ APP  $647.72 → $655.91 (+1.3%)  90% conf  Low risk   │   │
│ │ MU   $345.09 → $349.86 (+1.4%)  90% conf  Low risk   │   │
│ │ KLAC $1400 → $1420 (+1.4%)      90% conf  Low risk   │   │
│ └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│ All Stocks                                                   │
│ [Search: ___] [Filter: All ▼] [Sort: Confidence ▼]             │
│ ┌────┬────────┬────────┬────────┬──────┬────────┬────────┐    │
│ │ #  │ Symbol │ Price  │ Target │ Chg  │ Conf   │ Rec    │    │
│ ├────┼────────┼────────┼────────┼──────┼────────┼────────┤    │
│ │ 1  │ APP    │ 647.72 │ 655.91 │ +1.3%│ 90%    │ BUY │    │
│ │ 2  │ MU     │ 345.09 │ 349.86 │ +1.4%│ 90%    │ BUY │    │
│ └────┴────────┴────────┴────────┴──────┴────────┴────────┘    │
│ [1] [2] [3] ... [18] →                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**

- Header with navigation
- 4 KPI cards (responsive grid)
- 2 chart sections (side-by-side)
- Opportunity highlight section
- Filterable/sortable data table
- Pagination

---

### Page 2: Projections Detail

**Layout:**

```text
┌─────────────────────────────────────────────────────────────────┐
│ Projections - 5 Day Outlook                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Target Date: January 16, 2026  |  177 Projections Generated    │
│                                                                  │
│ ┌─ Tabs ────────────────────────────────────────────────────┐  │
│ │ [Strong Buy] [Buy] [Hold] [Sell] [Strong Sell]            │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│ STRONG BUY (11 stocks)                                       │
│                                                                  │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ APP - AppLovin Corp                          [View Detail] │ │
│ │ ───────────────────────────────────────────────────────────│ │
│ │ Current: $647.72  →  Target: $655.91  (+1.3%)             │ │
│ │ Confidence: ████████████████████ 90%                       │ │
│ │ Risk: Low  |  Trend: ↗ Bullish  |  Momentum: 85.2      │ │
│ │                                                             │ │
│ │ Reason: Strong +5.1% gain; very strong momentum;           │ │
│ │         low volume caution                                 │ │
│ │                                                             │ │
│ │ Price Targets:  Low: $650  |  Mid: $655  |  High: $661    │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ [More cards for each stock...]                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**

- Tab-based filtering by recommendation
- Expandable cards for each stock
- Visual confidence bars
- Color-coded risk levels
- Quick actions (compare, watchlist)

---

### Page 3: Stock Detail Modal

**Layout:**

```text
┌─────────────────────────────────────────────────────────────────┐
│ ✕                                                               │
│                                                                  │
│ AAPL - Apple Inc                                   [+ Watchlist]│
│ ──────────────────────────────────────────────────────────────  │
│                                                                  │
│ Current: $259.37  (+0.33 / +0.13%)                              │
│ Target:  $262.50  (+$3.13 / +1.2%)                              │
│                                                                  │
│ BUY  |  Confidence: 75%  |  Risk: Low                        │
│                                                                  │
│ ┌─ Tabs ───────────────────────────────────────────────────┐   │
│ │ [Overview] [Historical] [Technical] [News]               │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ Price Chart (30 days)                                           │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ 270 ┤                                          ╭─           │ │
│ │ 265 ┤                                   ╭──────╯            │ │
│ │ 260 ┤                          ╭────────╯                   │ │
│ │ 255 ┤                 ╭────────╯                            │ │
│ │ 250 ┤        ╭────────╯                                     │ │
│ │     └─────────────────────────────────────────────────     │ │
│ │     Dec 12          Dec 26          Jan 9                   │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Key Metrics                                                     │
│ ├─ Volume:       45,000,000                                     │
│ ├─ Market Cap:   $3.5T                                          │
│ ├─ Momentum:     65.5                                           │
│ ├─ Volatility:   15.2%                                          │
│ └─ RSI:          58.3                                           │
│                                                                  │
│ Projection History                                              │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Date       │ Rec  │ Conf │ Target │ Actual │ Accuracy      │ │
│ ├────────────┼──────┼──────┼────────┼────────┼───────────────┤ │
│ │ 2026-01-07 │ BUY  │ 72%  │ $258   │ $259   │ ✓ 99.6%       │ │
│ │ 2026-01-04 │ HOLD │ 68%  │ $255   │ $256   │ ✓ 99.2%       │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ [Close]                                           [Compare →]   │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**

- Tabbed interface for different data views
- Interactive price chart with zoom
- Key metrics display
- Historical projection accuracy
- Comparison tool

---

### Page 4: Historical Trends

**Layout:**

```text
┌─────────────────────────────────────────────────────────────────┐
│ Historical Trends                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Date Range: [Jan 1, 2026 ▼] to [Jan 11, 2026 ▼]   [Apply]     │
│                                                                  │
│ Market Performance Over Time                                    │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ 200 ┤                                                        │ │
│ │ 180 ┤              ╭─────────────────────────╮              │ │
│ │ 160 ┤      ╭───────╯                         ╰──╮           │ │
│ │ 140 ┤  ────╯                                    ╰───        │ │
│ │     └──────────────────────────────────────────────────     │ │
│ │        Jan 2    Jan 4     Jan 7     Jan 9    Jan 11         │ │
│ │                                                               │ │
│ │ Legend: ─ Stocks Tracked  ─ Avg Confidence  ─ Projections  │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Recommendation Trends                                           │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ [Stacked Area Chart]                                        │ │
│ │ Shows distribution of BUY/HOLD/SELL over time              │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Top Consistent Performers                                       │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Symbol │ Avg Confidence │ Consistency │ Avg Return          │ │
│ ├────────┼────────────────┼─────────────┼─────────────────────┤ │
│ │ AAPL   │ 78%            │ 95%         │ +2.3%              │ │
│ │ MSFT   │ 76%            │ 93%         │ +1.8%              │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Projection Accuracy                                             │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Overall Accuracy: 94.2%                                     │ │
│ │ Best Performing: STRONG BUY (96.8% accurate)                │ │
│ │ Needs Improvement: SELL (89.1% accurate)                    │ │
│ └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**

- Date range selector
- Multi-line time series charts
- Stacked area charts for distributions
- Performance metrics table
- Accuracy tracking

---

## Features Breakdown

### Phase 1: MVP (Week 1)

**Core Dashboard:**

- Market overview (KPI cards)
- Top gainers/losers chart
- Recommendation distribution pie chart
- STRONG BUY opportunities section
- Filterable stock table
- Basic stock detail view

**API:**

- `/api/market/overview`
- `/api/projections/summary`
- `/api/projections/opportunities`
- `/api/stocks/{symbol}`
- `/api/market/movers`

**Tech:**

- FastAPI backend reading CSV/JSON
- React frontend with TailwindCSS
- Recharts for visualizations
- Local development setup

---

### Phase 2: Enhanced Features (Week 2)

**Historical Analysis:**

- Historical trends page
- `/api/stocks/{symbol}/historical`
- Projection accuracy tracking
- Time-series charts with zoom
- Comparison tool (compare 2+ stocks)

**Improved UX:**

- Dark mode toggle
- Watchlist feature
- Export data (CSV/JSON)
- Keyboard shortcuts
- Mobile responsive design

**Performance:**

- Data caching (in-memory)
- Lazy loading for tables
- Optimized chart rendering

---

### Phase 3: Advanced Features (Future)

**Real-Time Updates:**

- WebSocket connection for live data
- Auto-refresh indicator
- Live price updates

**Advanced Analytics:**

- Sector analysis
- Correlation heatmaps
- Risk-return scatter plots
- Custom screening filters

**Integration:**

- Alert system integration (from ALERTING_DESIGN.md)
- User authentication
- Multiple portfolio support
- API rate limiting

---

## Design System

### Color Palette

**Semantic Colors:**

```css
/* Recommendations */
--strong-buy: #10B981    /* Green 500 */
--buy: #34D399           /* Green 400 */
--hold: #64748B          /* Slate 500 */
--sell: #F59E0B          /* Amber 500 */
--strong-sell: #EF4444   /* Red 500 */

/* Risk Levels */
--risk-low: #10B981      /* Green 500 */
--risk-medium: #F59E0B   /* Amber 500 */
--risk-high: #EF4444     /* Red 500 */

/* Trends */
--bullish: #10B981       /* Green 500 */
--neutral: #64748B       /* Slate 500 */
--bearish: #EF4444       /* Red 500 */

/* UI */
--background: #F8FAFC    /* Slate 50 */
--surface: #FFFFFF       /* White */
--primary: #3B82F6       /* Blue 500 */
--text-primary: #0F172A  /* Slate 900 */
--text-secondary: #64748B /* Slate 500 */
--border: #E2E8F0        /* Slate 200 */
```

### Typography

```css
/* Font Family */
font-family: 'Inter', -apple-system, system-ui, sans-serif;

/* Sizes */
--text-xs: 0.75rem;      /* 12px */
--text-sm: 0.875rem;     /* 14px */
--text-base: 1rem;       /* 16px */
--text-lg: 1.125rem;     /* 18px */
--text-xl: 1.25rem;      /* 20px */
--text-2xl: 1.5rem;      /* 24px */
--text-3xl: 1.875rem;    /* 30px */
```

### Components

**Buttons:**

- Primary: Blue background, white text, hover shadow
- Secondary: White background, blue text, border
- Danger: Red background, white text

**Cards:**

- White background
- Border: 1px solid slate-200
- Border radius: 8px
- Shadow: sm on hover

**Badges:**

- Recommendation badges: Rounded, colored background
- Risk badges: Small, pill-shaped
- Trend indicators: Icon + text

---

## Responsive Design

### Breakpoints

```css
/* Mobile First Approach */
sm: 640px   /* Tablets */
md: 768px   /* Small laptops */
lg: 1024px  /* Desktops */
xl: 1280px  /* Large desktops */
2xl: 1536px /* Extra large */
```

### Mobile Layout (< 768px)

- Stack KPI cards vertically
- Charts take full width
- Table scrolls horizontally
- Hamburger menu for navigation
- Bottom navigation bar

### Tablet Layout (768px - 1024px)

- 2-column grid for KPI cards
- Charts side-by-side (if space)
- Table with reduced columns
- Sidebar collapsible

### Desktop Layout (> 1024px)

- 4-column grid for KPI cards
- Charts side-by-side
- Full table with all columns
- Persistent sidebar

---

## Performance Considerations

### Backend Optimization

**Data Loading:**

- Load only latest CSV/JSON by default
- Cache parsed data in memory (5-minute TTL)
- Lazy load historical data on demand
- Index data by symbol for fast lookups

**API Response:**

- Compress responses (gzip)
- Paginate large datasets
- Return only requested fields
- Use HTTP caching headers

**Example Cache Strategy:**

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=128)
def get_latest_projections(cache_buster: str):
    # cache_buster changes every 5 minutes
    return load_projection_data()

# In endpoint
cache_key = datetime.now().strftime("%Y%m%d%H%M") // 5
projections = get_latest_projections(cache_key)
```

### Frontend Optimization

**Code Splitting:**

- Lazy load routes (React.lazy)
- Lazy load heavy charts
- Defer non-critical scripts

**Data Fetching:**

- Use SWR for automatic caching & revalidation
- Prefetch on hover
- Optimistic updates for better UX

**Rendering:**

- Virtualize long tables (react-virtual)
- Memoize expensive components
- Debounce search/filter inputs

---

## Deployment

### Development Setup

```bash
# Backend
cd dashboard/backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd dashboard/frontend
npm install
npm start  # Runs on port 3000
```

### Production Deployment

**Backend (Railway/Render/Fly.io):**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend (Vercel/Netlify):**

```bash
# Build
npm run build

# Deploy (automatic via git push)
vercel --prod
# or
netlify deploy --prod
```

**Environment Variables:**

```bash
# Backend
DATA_DIR=/path/to/market-helm/data
CORS_ORIGINS=https://your-frontend.vercel.app

# Frontend
REACT_APP_API_URL=https://your-backend.railway.app
```

---

## Testing Strategy

### Backend Tests

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from dashboard.backend.main import app

client = TestClient(app)

def test_market_overview():
    response = client.get("/api/market/overview")
    assert response.status_code == 200
    assert "totalStocks" in response.json()
    assert response.json()["totalStocks"] > 0

def test_projections_summary():
    response = client.get("/api/projections/summary")
    assert response.status_code == 200
    data = response.json()
    assert "totalProjections" in data
    assert "recommendations" in data

def test_stock_detail():
    response = client.get("/api/stocks/AAPL")
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"
```

### Frontend Tests

```typescript
// components/KPICard.test.tsx
import { render, screen } from '@testing-library/react';
import KPICard from './KPICard';

test('renders KPI card with correct value', () => {
  render(<KPICard title="Total Stocks" value="196" />);
  expect(screen.getByText('Total Stocks')).toBeInTheDocument();
  expect(screen.getByText('196')).toBeInTheDocument();
});

// hooks/useMarketData.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import useMarketData from './useMarketData';

test('fetches market data successfully', async () => {
  const { result } = renderHook(() => useMarketData());
  
  await waitFor(() => {
    expect(result.current.data).toBeDefined();
    expect(result.current.loading).toBe(false);
  });
});
```

### E2E Tests (Playwright)

```typescript
// e2e/dashboard.spec.ts
import { test, expect } from '@playwright/test';

test('dashboard loads and displays data', async ({ page }) => {
  await page.goto('http://localhost:3000');
  
  // Check KPI cards load
  await expect(page.locator('text=Stocks Tracked')).toBeVisible();
  
  // Check table loads
  await expect(page.locator('table')).toBeVisible();
  
  // Check search works
  await page.fill('input[placeholder*="Search"]', 'AAPL');
  await expect(page.locator('text=AAPL')).toBeVisible();
});

test('stock detail modal opens', async ({ page }) => {
  await page.goto('http://localhost:3000');
  
  // Click first stock row
  await page.click('table tbody tr:first-child');
  
  // Modal should open
  await expect(page.locator('[role="dialog"]')).toBeVisible();
  await expect(page.locator('text=Price Chart')).toBeVisible();
});
```

---

## Security Considerations

### API Security

- **CORS:** Restrict to known frontend origins
- **Rate Limiting:** 100 requests per minute per IP
- **Input Validation:** Validate all query parameters
- **Error Handling:** Don't leak internal errors

### Data Privacy

- No user data collected (read-only dashboard)
- No authentication required for MVP
- API keys stored in environment variables (not in code)

### Production Checklist

- [ ] HTTPS enabled
- [ ] CORS configured correctly
- [ ] Rate limiting active
- [ ] Error monitoring (Sentry)
- [ ] API logging enabled
- [ ] Regular security updates

---

## Future Enhancements

### Advanced Visualizations

- Candlestick charts for price history
- Volume profile charts
- Technical indicator overlays (RSI, MACD, Bollinger Bands)
- Correlation matrix heatmap
- Risk-return scatter plot

### User Features

- User accounts & authentication
- Custom watchlists
- Portfolio tracking
- Alert configuration UI
- Custom dashboard layouts
- Theme customization

### Data Features

- Real-time WebSocket updates
- Intraday data (if API supports)
- News integration
- Social sentiment analysis
- Earnings calendar
- Dividend information

### Export & Sharing

- Export to Excel/PDF
- Share dashboard snapshots
- Email reports
- Webhook integrations

---

## Success Metrics

### Phase 1 Goals

- Dashboard loads in < 2 seconds
- All 177 projections visible
- Mobile responsive (works on phones)
- 95%+ uptime

### Phase 2 Goals

- Historical data for 30+ days
- Projection accuracy tracking
- Dark mode implemented
- < 1 second search/filter response

### Phase 3 Goals

- Real-time updates (< 5s latency)
- User authentication
- Alert system integration
- 1000+ page views per day

---

## Documentation Requirements

### User Documentation

- [ ] Getting Started Guide
- [ ] Dashboard User Manual
- [ ] FAQ
- [ ] Keyboard Shortcuts Reference

### Developer Documentation

- [ ] API Documentation (auto-generated Swagger)
- [ ] Component Library (Storybook)
- [ ] Contributing Guide
- [ ] Deployment Guide

---

## Timeline

### Week 1: MVP Development

#### Days 1-2: Backend Setup

- FastAPI project structure
- Data loading services
- Core API endpoints
- Basic testing

#### Days 3-4: Frontend Setup

- React + TypeScript setup
- Component library setup
- API integration
- Dashboard layout

#### Days 5-7: MVP Features

- KPI cards
- Charts integration
- Stock table
- Stock detail modal
- Testing & bug fixes

### Week 2: Enhancement & Polish

#### Days 8-9: Historical Features

- Historical data endpoints
- Time-series charts
- Projection accuracy
- Comparison tool

#### Days 10-11: UX Improvements

- Dark mode
- Mobile optimization
- Loading states
- Error handling

#### Days 12-14: Deployment & Testing

- Production deployment
- E2E testing
- Performance optimization
- Documentation

---

## Contributing

Want to help build the dashboard? See [CONTRIBUTING.md](../CONTRIBUTING.md)

**Open work (examples — see [PROJECT_STATUS.md](PROJECT_STATUS.md)):**

- Dashboard: lazy-loaded routes / bundle size
- Dashboard: watchlist and keyboard shortcuts
- Dashboard: multi-stock compare, chart zoom polish
- Real-time updates and authentication (later phases)

**Contact:** Open an issue with tag `feature: dashboard` to discuss implementation.

---

## Related Documentation

- [Stock Projections Technical Docs](STOCK_PROJECTIONS.md)
- [Alerting System Design](ALERTING_DESIGN.md)
- [Main README](../README.md)
- [Contributing Guide](../CONTRIBUTING.md)

---

**Status:** Design spec — **Phase 1 MVP and much of Phase 2 (historical views, accuracy, dark mode, export)** are implemented in the repository. Remaining Phase 2/3 items (watchlist, lazy routes, WebSockets, auth) are tracked in [PROJECT_STATUS.md](PROJECT_STATUS.md).

**Next step for readers:** Use [dashboard/README.md](../dashboard/README.md) to run and develop the app; use this document for deeper UI/API reference.
