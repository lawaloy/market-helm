# MarketHelm

A stock market **monitoring** and analysis tool (CLI + web dashboard) that screens indices, fetches data, and projects short-term moves—aimed at growing toward suggestions, alerts, and (later) execution. Perfect for traders and analysts building a daily workflow.

**Direction:** The long-term goal is a product that **monitors** markets, **suggests** buys/sells, and can **eventually execute** via broker APIs—with room to grow from the installable **CLI** toward a **multi-user** app. Read the full picture in [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md#product-vision).

## What Does It Do?

This tool automatically:

1. **Screens** major stock indices (S&P 500, NASDAQ-100) to find active, high-volume stocks
2. **Fetches** real-time market data using official APIs (no scraping!)
3. **Analyzes** daily changes, identifies top gainers/losers
4. **Projects** 5-day price targets with buy/sell/hold recommendations
5. **Saves** results to CSV files and generates summary reports
6. **Logs** everything for troubleshooting and monitoring

**Run time:** ~4 minutes per day on the free tier.

### Web dashboard

**Visual, interactive UI** — same **`pip install market-helm`** as the CLI. The package includes the FastAPI server and a built React UI (no Node.js needed to use it).

```bash
market-helm-web
```

Open **<http://localhost:8000>** — API docs at **/docs**.

Develop the React UI (Vite on port 3000): [dashboard/README.md](dashboard/README.md#development-clone-hot-reload).  
Hosting and persistence: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Quick Start (Beginners Welcome!)

### Prerequisites

- Python 3.12 or higher ([Download here](https://www.python.org/downloads/))
- A free Finnhub API key ([Sign up here](https://finnhub.io/register) — takes 2 minutes)

### Step 1: Install

Create a virtual environment (recommended), then activate it:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

**Install the package—pick one:**

- **From PyPI** (recommended — includes CLI and dashboard):

  ```bash
  pip install market-helm
  ```

  - Package page: [pypi.org/project/market-helm](https://pypi.org/project/market-helm/)
  - Optional OpenAI summaries: `pip install 'market-helm[ai]'`

- **From source** (clone for development or to rebuild the dashboard UI):

  ```bash
  git clone https://github.com/lawaloy/market-helm.git
  cd market-helm
  pip install -e .
  ```

### Step 2: Add Your API Key

Create a `.env` file where you will run the tool:

```text
FINNHUB_API_KEY=your-api-key-here
```

*(Get your free key from [finnhub.io/register](https://finnhub.io/register))*

### Step 3: Run It

```bash
market-helm          # daily tracker → CSV/JSON under data/
market-helm-web      # web UI + API → http://localhost:8000
```

If you cloned the repo, you can also run **`python main.py`** from the project root.

Each tracker run screens ~201 stocks, selects the top movers, fetches detailed data, and saves `data/daily_data_YYYY-MM-DD.csv`.

---

## What You Get

| Output | Description |
|--------|-------------|
| `data/daily_data_YYYY-MM-DD.csv` | Prices, volume, daily changes |
| `data/summary_YYYY-MM-DD.json` | Gainers, losers, statistics |
| `logs/market_helm_YYYY-MM-DD.log` | Execution logs |

More entry points, console examples, and programmatic use: [docs/USAGE.md](docs/USAGE.md).

---

## Documentation

Full index: **[docs/README.md](docs/README.md)**

| Guide | Topics |
|-------|--------|
| [USAGE.md](docs/USAGE.md) | CLI options, dashboard, output files |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Indices, screening filters, performance |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, Kubernetes, `DATA_DIR`, secrets |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Code layout, workflow, rate limiting |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common errors, FAQ |
| [ADVANCED.md](docs/ADVANCED.md) | OpenAI summaries, custom providers |
| [PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | Roadmap, alerts, product vision |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Next priorities:** alerts delivery, projection accuracy, dashboard polish — details in [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

---

## License

MIT License — free to use, modify, and distribute. See [LICENSE](LICENSE).

## Author

**lawaloy** — [GitHub](https://github.com/lawaloy)
