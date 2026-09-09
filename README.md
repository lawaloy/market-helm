# MarketHelm

MarketHelm is a stock-market monitoring and analysis tool with a Python CLI and
a web dashboard. It screens major indices, fetches market data, produces
five-session projections, records results, and can deliver configured alerts.
Broker execution is not implemented.

For the evidence-based feature matrix and current priorities, see
[Project status](docs/PROJECT_STATUS.md).

## What runs where?

| Mode             | Command or entry point            | What runs                                       | Open in a browser                       |
| ---------------- | --------------------------------- | ----------------------------------------------- | --------------------------------------- |
| Daily tracker    | `market-helm`                     | CLI workflow; writes CSV/JSON data              | Nothing                                 |
| Packaged web app | `market-helm-web`                 | FastAPI API and compiled React UI on one server | <http://localhost:8000>                 |
| Web development  | FastAPI on 8000 plus Vite on 3000 | API and hot-reloading React UI                  | <http://localhost:3000>                 |
| Hosted staging   | `docker-compose.staging.yml`      | PostgreSQL, API/compiled UI, and alert worker   | The hostname configured by the operator |

The production web image does **not** require a separately hosted frontend.
[`Dockerfile.web`](Dockerfile.web) builds React and copies it into the FastAPI
image, which serves both the UI and `/api/*` on port 8000.

The repository currently provides portable deployment artifacts, not a live
public MarketHelm URL or a selected cloud provider. Provider selection, DNS/TLS,
managed PostgreSQL, email delivery, and external monitoring remain operator
sign-off tasks in [Deployment and persistence](docs/DEPLOYMENT.md#external-staging-sign-off).

## Quick start

### Requirements

- Python 3.12 or newer
- A [Finnhub API key](https://finnhub.io/register) for fetching live market data
- Node.js is needed when running from a source checkout because the ignored
  React build output must be created locally. Published packages already include it.

Create and activate a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

### Fastest local preview: published package

Install from PyPI and start the integrated UI and API:

```bash
pip install market-helm
market-helm-web
```

Open <http://localhost:8000>. API documentation is available at
<http://localhost:8000/docs>.

### Local preview from a source checkout

Install the Python package, install the locked frontend dependencies, and build
the React application once:

```bash
pip install -e .
cd dashboard/frontend
npm ci
npm run build
cd ../..
market-helm-web
```

Open <http://localhost:8000>. For frontend hot reload instead of an integrated
build, use the focused [dashboard development guide](dashboard/README.md).

### Fetch market data

The dashboard can start without an API key or saved data, but its market views
remain empty until data has been fetched. Create `.env` in the directory where
you will run MarketHelm:

```text
FINNHUB_API_KEY=your-api-key-here
```

Run the tracker to fetch and save data:

```bash
market-helm
```

## Projection validation

Evaluate saved projections against exact NYSE trading sessions:

```bash
market-helm backtest --data-dir data --days 365 --output data/backtest.json
```

Verify the committed projection-evaluator scenario baseline:

```bash
python3 scripts/projection_baseline.py check
```

Assess whether local forward-generated outcomes meet the real-data evidence
gate:

```bash
python3 scripts/projection_baseline.py assess --data-dir data --days 365
```

## Runtime data

| Output                            | Description                       |
| --------------------------------- | --------------------------------- |
| `data/daily_data_YYYY-MM-DD.csv`  | Prices, volume, and daily changes |
| `data/projections_YYYY-MM-DD.csv` | Saved projection observations     |
| `data/summary_YYYY-MM-DD.json`    | Gainers, losers, and statistics   |
| `logs/market_helm_YYYY-MM-DD.log` | Execution logs                    |

Runtime data and credentials are not deployed from Git. Set `DATA_DIR` to an
absolute persistent path when hosting the application.

## Documentation

Use the [documentation index](docs/README.md) to find the single authoritative
guide for each topic:

| Topic                                      | Guide                                      |
| ------------------------------------------ | ------------------------------------------ |
| Commands and output files                  | [Usage](docs/USAGE.md)                     |
| Settings and providers                     | [Configuration](docs/CONFIGURATION.md)     |
| Hosting, persistence, workers, and secrets | [Deployment](docs/DEPLOYMENT.md)           |
| Components and operating modes             | [Architecture](docs/ARCHITECTURE.md)       |
| Current capabilities and roadmap           | [Project status](docs/PROJECT_STATUS.md)   |
| Common failures                            | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Development and pull requests              | [Contributing](CONTRIBUTING.md)            |

## License

MarketHelm is available under the [MIT License](LICENSE).
