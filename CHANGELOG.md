# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**PyPI and Git today:** releases use tags **`v0.2.x`** (for example **`v0.2.9`**). The canonical Python version in **`setup.cfg`** matches that line; dashboard copies stay in sync via **`scripts/version_sync.py`**.

**Ordering:** sections below are **newest first by release date**. Headings like **`[0.5.0]`** / **`[0.4.0]`** describe **historical** distribution and branding changes (e.g. **`market-desk`** → **`market-helm`**); they are not parallel “current” PyPI lines.

## [Unreleased]

### Added

- **Alerts product:** Helmtower configuration, live quote picker, test sends,
  looping and database-backed workers, retry/backoff, and delivery history.
- **Notification channels:** SMTP, SendGrid, and Mailgun email plus generic, Slack,
  and Discord webhooks.
- **Hosted accounts:** Registration, sessions, tenant-isolated alerts, email
  verification, password reset/change, logout/session invalidation, and account
  deletion.
- **Hosted persistence and operations:** SQLite/PostgreSQL storage, versioned
  migrations, worker jobs, shared rate limiting, liveness/readiness/worker health,
  and metrics.

### Not yet shipped

- **Alerts:** Technical/multi-condition rules and SMS/push channels (see
  [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)).
- **Dashboard:** Route-level code splitting, watchlist, keyboard shortcuts (see [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)).
- **Real-time:** WebSocket or streaming-style updates (batch/daily today).
- **Execution:** Broker integration and automated order placement.

## [0.3.4] - 2026-08-21

### Changed

- Repository version metadata aligned with Git tag **`v0.3.4`** / PyPI **`0.3.4`** (automated post-release sync).


## [0.3.3] - 2026-08-11

### Changed

- Repository version metadata aligned with Git tag **`v0.3.3`** / PyPI **`0.3.3`** (automated post-release sync).


## [0.3.2] - 2026-07-29

### Changed

- Repository version metadata aligned with Git tag **`v0.3.2`** / PyPI **`0.3.2`** (automated post-release sync).


## [0.2.16] - 2026-05-21

### Changed

- Repository version metadata aligned with Git tag **`v0.2.16`** / PyPI **`0.2.16`** (automated post-release sync).


## [0.2.15] - 2026-05-21

### Changed

- Repository version metadata aligned with Git tag **`v0.2.15`** / PyPI **`0.2.15`** (automated post-release sync).


## [0.2.14] - 2026-04-12

### Changed

- Repository version metadata aligned with Git tag **`v0.2.14`** / PyPI **`0.2.14`** (automated post-release sync).


## [0.2.9] - 2026-04-12

### Changed

- Aligned repository version metadata with Git tag **`v0.2.9`** / PyPI **`0.2.9`**: `setup.cfg`, `dashboard/frontend/package.json`, `package-lock.json` (root), `dashboard/backend/main.py`.

## [0.2.8] - 2026-04-11

### Documentation

- Synced the documentation set with shipped historical trends, projection
  accuracy, and the alerting behavior available at that release.
- Aligned package metadata with the **`v0.2.*`** release tag line (follows **`v0.2.7`**).

## [0.5.0] - 2026-03-26

### Changed

- **Product branding:** **MarketHelm** (display name).
- **GitHub repository:** **`lawaloy/market-helm`**.
- **PyPI distribution:** **`market-helm`** (`pip install market-helm`). CLI: **`market-helm`**, **`market-helm-web`** only.
- **User config/data (pip install):** **`~/.market-helm/`**. If it does not exist yet but **`~/.market-desk`** does, it is **renamed** to **`~/.market-helm`** on first use. Legacy log files named **`stock_tracker_*.log`** are **renamed** to **`market_helm_*.log`** when the logger starts.

## [0.4.0] - 2026-03-26

### Changed

- **PyPI distribution** evolved to **`market-desk`** to reflect scope beyond “tracking” (monitoring, dashboard, future alerts/execution).
- **CLI commands:** primary names are **`market-desk`** (daily run) and **`market-desk-web`** (dashboard server). *(Superseded in [0.5.0] by **`market-helm`** / **`market-helm-web`**.)*
- **User data/config (pip install), in 0.4.0 only:** new installs used **`~/.market-desk/`**. *(Superseded in [0.5.0] by **`~/.market-helm/`**; **`~/.market-desk`** may be auto-renamed.)*
- **Product branding** in docs: **Market Desk** (repository URL later standardized as **`lawaloy/market-helm`** in [0.5.0]).

## [0.3.1] - 2026-02-10

### Added

- **Dashboard Dark Mode**: Theme toggle with system preference detection and localStorage persistence
- **Dashboard Export**: CSV/PNG/PDF export for dashboard, stock table, and summary with clear labels per export target
- **Enhanced Mobile Layout**: Responsive design with horizontal scroll for stock tables

### Changed

- **Data Loader**: Uses date in filename (YYYY-MM-DD) instead of file mtime for latest data on startup and refresh
- **Header Layout**: Theme toggle moved to far right

## [0.3.0] - 2026-01-14

### Added

- **Web Dashboard**: Modern, interactive dashboard for visualizing stock data and projections
  - Real-time market overview with KPI cards (stocks tracked, confidence, expected move)
  - Interactive bar chart for top gainers/losers
  - Pie chart for recommendation distribution
  - Filterable and sortable stock table with pagination
  - STRONG BUY opportunities section highlighting best trades
  - Stock detail modal with projections, confidence, risk assessment
  - Search and filter functionality
  - Mobile-responsive design
- **FastAPI Backend**:
  - `/api/market/overview` - Market statistics and index breakdown
  - `/api/market/movers` - Top gainers and losers
  - `/api/projections/summary` - Projections overview and sentiment
  - `/api/projections/opportunities` - Filtered buy/sell opportunities
  - `/api/stocks/{symbol}` - Detailed stock information
  - `/api/stocks/{symbol}/historical` - Historical price data
  - Auto-generated API documentation (Swagger/ReDoc)
  - CORS support for local development
  - Data caching and optimization
- **React Frontend**:
  - TypeScript for type safety
  - TailwindCSS for modern styling
  - Recharts for data visualization
  - Headless UI for accessible modals
  - Custom hooks for data fetching
  - Responsive design for all screen sizes
- **Developer Tools**:
  - Startup scripts for Windows (`.bat`) and Unix (`.sh`)
  - Comprehensive dashboard documentation
  - Vite for fast development and builds

### Changed

- Updated main README with dashboard quick start
- Enhanced project structure with dashboard folder

## [0.2.0] - 2026-01-07

### Added

- **Stock Projection System**: Comprehensive 5-day price projection and recommendation engine
  - Technical analysis with momentum and volatility calculations
  - Bullish/bearish trend classification
  - Price targets (high/mid/low) with confidence scores
  - Risk assessment (Low/Medium/High)
  - Actionable recommendations (STRONG BUY to STRONG SELL)
- **Markdown Report Generation**: Human-readable projection reports for product teams
- **Projection CLI Display**: Enhanced console output with top buy/sell opportunities
- **Comprehensive Test Suite**: Unit tests for projection system
- **Documentation**: Technical documentation for stock projections feature
- **Markdown Linting**: Automated quality assurance for all markdown files

### Changed

- Enhanced data storage to support projection data in CSV and Markdown formats
- Updated workflow to integrate projection generation
- Made OpenAI dependency optional (moved to extras_require)

### Fixed

- Various markdown linting issues across documentation files

## [0.1.0] - 2026-01-02

### Added

- Initial release
- Stock screening for S&P 500 and NASDAQ-100
- Real-time data fetching via Finnhub API
- Daily market analysis with top gainers/losers
- Index comparison (SPY, QQQ)
- CSV and JSON data export
- Optional AI-powered summaries (OpenAI integration)
- Command-line interface
- Docker support
- Kubernetes CronJob configuration
- GitHub Actions for daily automated runs
- Comprehensive logging system
