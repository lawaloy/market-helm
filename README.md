# Stock Exchange Tracker

A daily stock market tracking tool that automatically identifies promising stocks, fetches market data, and generates insights. Perfect for traders, analysts, or anyone interested in tracking market trends.

**Direction:** The long-term goal is a product that **monitors** markets, **suggests** buys/sells, and can **eventually execute** via broker APIs—with room to grow from the installable **CLI** toward a **multi-user** app. Read the full picture in [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md#product-vision).

## What Does It Do?

This tool automatically:

1. **Screens** major stock indices (S&P 500, NASDAQ-100) to find active, high-volume stocks
2. **Fetches** real-time market data using official APIs (no scraping!)
3. **Analyzes** daily changes, identifies top gainers/losers
4. **Projects** 5-day price targets with buy/sell/hold recommendations
5. **Saves** results to CSV files and generates summary reports
6. **Logs** everything for troubleshooting and monitoring

**Run time**: ~4 minutes per day on the free tier

### NEW: Web Dashboard (v0.3.0)

**Visual, interactive dashboard** is now available! Explore stock data, projections, and recommendations in a modern React interface.

**Quick Start:**

```bash
# Start backend
cd dashboard/backend && python main.py

# Start frontend (in another terminal)
cd dashboard/frontend && npm install && npm run dev
```

Visit `http://localhost:3000` to see it in action!

See [Dashboard README](dashboard/README.md) for full setup instructions.

**Hosting:** Deploying the API and frontend, setting **`DATA_DIR`** on persistent disk, and keeping secrets out of git — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Quick Start (Beginners Welcome!)

### Prerequisites

- Python 3.12 or higher ([Download here](https://www.python.org/downloads/))
- A free Finnhub API key ([Sign up here](https://finnhub.io/register) - takes 2 minutes)

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

- **From PyPI** (simplest if you only need the CLI):

  ```bash
  pip install stock-exchange-tracker
  ```

  - Package page: [pypi.org/project/stock-exchange-tracker](https://pypi.org/project/stock-exchange-tracker/)
  - Optional OpenAI-powered summaries: `pip install 'stock-exchange-tracker[ai]'`

- **From source** (clone the repo for development, or to run the [web dashboard](dashboard/README.md) from this tree):

  ```bash
  git clone https://github.com/lawaloy/stock-exchange-tracker.git
  cd stock-exchange-tracker
  pip install -e .
  ```

**Why isn’t the web dashboard installed from PyPI?** The published package (`stock-exchange-tracker` on PyPI) only includes the **`src/`** library and the **`stock-tracker`** CLI—it does not bundle the dashboard. The dashboard is a **separate stack**: a **FastAPI** backend plus a **React** frontend that must be built with **Node.js** (`npm install` / `npm run build`). Shipping that through `pip` would mean packaging prebuilt static assets and extra dependencies into the wheel (or publishing a separate npm package)—**we haven’t done that yet**. To run the UI, use a **clone** of the repo and follow [dashboard/README.md](dashboard/README.md).

### Step 2: Add Your API Key

Create a file named `.env` in the folder where you will run the tool (project root if you cloned, or any working directory if you installed from PyPI):

```text
FINNHUB_API_KEY=your-api-key-here
```

*(Get your free key from [finnhub.io/register](https://finnhub.io/register))*

### Step 3: Run It

The install adds the **`stock-tracker`** command:

```bash
stock-tracker
```

If you cloned the repository, you can also run:

```bash
python main.py
```

from the project root (same CLI under the hood).

That's it! The tool will:

- Screen 201 stocks from major indices
- Select the top 20 most active stocks
- Fetch detailed data and analyze trends
- Save results to `data/daily_data_YYYY-MM-DD.csv`

---

## What You Get

### Output Files

- **`data/daily_data_YYYY-MM-DD.csv`**: Full stock data (prices, volume, changes)
- **`data/summary_YYYY-MM-DD.json`**: Analysis summary (gainers, losers, statistics)
- **`logs/stock_tracker_YYYY-MM-DD.log`**: Detailed execution logs

### Console Output

```text
Top 5 Gainers:
  1. MU (Micron Technology): +10.51% @ $315.42
  2. WDC (Western Digital): +8.96% @ $187.70
  ...

Top 5 Losers:
  1. PLTR (Palantir): -5.56% @ $167.86
  ...

Index Performance:
  S&P 500: Avg Change +1.82% (23 gainers | 7 losers)
  NASDAQ-100: Avg Change +0.01% (12 gainers | 18 losers)
```

---

## Running the Tracker (Multiple Ways)

### Option 1: CLI Interface (Recommended for Daily Use)

```bash
# Main entry point - formatted console output
python main.py
```

This runs the CLI interface which:

- Shows formatted console output
- Displays top gainers/losers
- Shows index performance
- Prints AI summary (if enabled)

### Option 2: Direct CLI Module

```bash
# Run CLI module directly
python -m src.cli.commands
```

Same as Option 1, just a different way to invoke it.

### Option 3: Direct Workflow (Programmatic)

```bash
# Run workflow without CLI formatting
python -m src.workflows.tracker
```

This runs the core workflow and returns structured JSON data. Useful for:

- Testing the workflow logic
- Integrating into other Python scripts
- CI/CD pipelines
- Debugging

### Option 4: Programmatic Import (Python Scripts)

```python
from src.workflows.tracker import StockTrackerWorkflow

# Run the workflow
workflow = StockTrackerWorkflow()
result = workflow.run(use_screener=True)

# Access structured data
if result["success"]:
    analysis = result["analysis"]
    top_gainers = analysis["top_gainers"]
    ai_summary = result.get("ai_summary")
    # ... use the data in your application
```

This is ideal for:

- Building a web API
- Creating custom dashboards
- Integrating with other systems
- Scheduled tasks with custom notifications

---

## Configuration

### What Stocks to Track

Edit `config/exchanges.json`:

```json
{
  "indices_to_track": [
    "S&P 500",
    "NASDAQ-100"
  ]
}
```

### Screening Filters

Edit `config/filters.json` to adjust what qualifies as a "good" stock:

```json
{
  "volume_threshold": 1000000,     // Minimum daily volume
  "price_min": 5.0,                 // Minimum stock price
  "price_max": 500.0,               // Maximum stock price
  "min_daily_change_pct": 2.0,      // Minimum % move (filters quiet stocks)
  "market_cap_min": 1000000000,     // Minimum market cap ($1B)
  "top_n": 30                       // How many stocks to track
}
```

**Tip**: Lower `top_n` to run even faster (currently optimized at 20 for ~4 min runs)

---

## Production Deployment

### Docker

```bash
docker build -t stock-tracker:latest .
docker run --rm -e FINNHUB_API_KEY=your-key stock-tracker:latest
# Or: docker run --rm --env-file .env stock-tracker:latest
```

**Schedule daily runs**: Use cron (Linux/Mac), Task Scheduler (Windows), or systemd. Example cron:

```bash
0 9 * * * docker run --rm -e FINNHUB_API_KEY=$(cat /path/to/key) stock-tracker:latest >> /var/log/stock-tracker.log 2>&1
```

### Docker Compose

```yaml
services:
  stock-tracker:
    build: .
    environment:
      - FINNHUB_API_KEY=${FINNHUB_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

### Kubernetes

Use `k8s/stock-tracker-cronjob.yaml` as a CronJob. Create secrets first:

```bash
kubectl create secret generic stock-tracker-secrets \
  --from-literal=FINNHUB_API_KEY=your-key \
  --from-literal=OPENAI_API_KEY=your-key
```

### Cloud

AWS ECS + EventBridge, GCP Cloud Run + Scheduler, Azure Container Instances + Logic Apps — store keys in secret manager, trigger daily.

### Security

- Never commit keys; `.env` is gitignored
- Use secret stores in production (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)
- Rotate keys periodically; audit Finnhub usage

---

## Understanding the Code

### Project Structure

```text
stock-exchange-tracker/
├── main.py                     # Entry point (run this!)
├── src/
│   ├── __init__.py             # Package initialization
│   ├── core/                   # Core utilities
│   │   ├── config.py           # Configuration loader
│   │   └── logger.py           # Logging setup
│   ├── services/               # External data services
│   │   ├── api_client.py       # Finnhub API client (rate limiting, retries)
│   │   ├── index_fetcher.py    # Gets stock lists from indices
│   │   ├── stock_screener.py   # Filters stocks by volume/activity
│   │   └── data_fetcher.py     # Fetches detailed stock data
│   ├── analysis/               # Data analysis & AI
│   │   ├── analyzer.py         # Computes gainers/losers/stats
│   │   └── ai_summarizer.py    # AI-powered market summaries
│   ├── storage/                # Data persistence
│   │   └── data_storage.py     # Saves CSV/JSON files
│   ├── workflows/              # Business logic (reusable)
│   │   └── tracker.py          # Core workflow orchestration
│   └── cli/                    # CLI interface (presentation)
│       └── commands.py         # Command-line interface
├── config/
│   ├── exchanges.json          # Which indices to track
│   └── filters.json            # Screening criteria
├── data/                       # Output files (CSV, JSON)
└── logs/                       # Execution logs
```

### How It Works

1. **Index Fetching**: Gets stock symbols from S&P 500 (first 100), NASDAQ-100
2. **Screening** (1 API call per stock): Quick check of price/volume to filter candidates
3. **Data Fetching** (2 API calls per qualified stock): Get detailed data for top 20 stocks
4. **Analysis**: Calculate changes, identify trends
5. **Storage**: Save to CSV/JSON

### Rate Limiting

- **Free tier**: 60 API calls per minute
- **Current setup**: ~241 total calls (~4 minutes)
- **How we stay under limit**:
  - Screening uses lightweight 1-call method (quote only)
  - Only 20 qualified stocks get full 2-call fetch (quote + profile)
  - S&P 500 capped at 100 stocks for screening
  - 2 parallel workers with staggered starts
  - Automatic pauses every 25-50 requests

---

## Troubleshooting

### API key required

- Make sure `.env` file exists with `FINNHUB_API_KEY=your-key`
- Check the key is correct (40 characters)
- Restart terminal after creating `.env`

### Rate limit exceeded (429)

- The tool has built-in retry logic
- If it happens frequently:
  - Lower `top_n` in `config/filters.json`
  - Wait 5-10 minutes between runs
  - Consider upgrading to Finnhub paid tier

### No data fetched

- Check internet connection
- Verify Finnhub API key is valid
- Check `logs/stock_tracker_errors_*.log` for details

### Logs not showing?

- Logs are in `logs/` folder (created automatically)
- Console shows INFO level, files show DEBUG level

---

## Advanced Topics

### AI-Powered Market Summaries (Optional)

By default, the tool generates basic market summaries from templates. Want **natural language AI summaries** instead? Add OpenAI!

**What you get with OpenAI:**

```text
Market Summary for YYYY-MM-DD:

Today's market showed strong momentum with technology stocks leading the charge. 
The top gainer, Micron Technology (MU), surged 10.51% on strong earnings expectations, 
while semiconductor stocks broadly outperformed. The S&P 500 averaged a +1.82% gain 
with 23 stocks advancing against only 7 declining, indicating broad-based strength. 
However, select technology stocks like Palantir (PLTR) saw profit-taking with a 
-5.56% decline after recent gains...
```

**What you get without OpenAI (demo mode):**

```text
Market Summary for YYYY-MM-DD:
Top gainer: MU +10.51%
Top loser: PLTR -5.56%
Overall market: Mixed with 23 gainers and 7 losers
```

#### Setup (takes 3 minutes)

1. **Get an OpenAI API key** (costs ~$0.01-0.05 per summary):
   - Visit: <https://platform.openai.com/signup>
   - Add payment method (pay-as-you-go, no monthly fees)
   - Generate API key from: <https://platform.openai.com/api-keys>

2. **Add to your `.env` file**:

   ```text
   FINNHUB_API_KEY=your-finnhub-key
   OPENAI_API_KEY=sk-proj-your-openai-key-here
   ```

3. **Run normally** - AI summaries are automatic!

```bash
python main.py
```

**Cost estimate**: ~$0.02/day for GPT-4 summaries (< $1/month for daily runs)

### Custom Providers

Want to use a different data provider? Edit `src/api_client.py` to add your provider's API calls.

---

## Performance Tips

### Run Faster

- **Lower `top_n`**: Currently at 20.
- **Track fewer indices**: Remove one from `config/exchanges.json`
- **Upgrade API tier**: Paid Finnhub plans allow more calls/minute

### Run Cheaper

- Keep free tier (60 calls/min)
- Run once per day (not multiple times) when the scheduler is enabled
- Use Docker for efficiency

---

## FAQ

**Q: Is this free?**  
A: Yes! Finnhub's free tier is sufficient for daily tracking.

**Q: Can I track other stocks?**  
A: Yes, edit `config/exchanges.json` to add symbols or change indices.

**Q: What if I miss a day?**  
A: Just rerun it. Each run is independent; data is saved with the date.

**Q: Can I backtest strategies?**  
A: This tool focuses on daily snapshots. For backtesting, you'd need historical data (not included).

**Q: Is my data private?**  
A: Yes. All data stays on your machine. API keys never leave your environment.

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

**Project status (what shipped, what’s next, gaps):** [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)

**Next priorities (summary):**

1. **Alerts** — Extend beyond log + webhook: **email (SMTP)**, optional Slack-formatted payloads, **CLI** commands; full vision in [ALERTING_DESIGN.md](docs/ALERTING_DESIGN.md).
2. **Projection accuracy** — Deeper metrics (e.g. by confidence), business-calendar targets as needed.
3. **Dashboard** — Watchlist, code splitting, shortcuts (see [dashboard/README.md](dashboard/README.md)).
4. **Broader product** — More exchanges/filters, richer AI summaries, sector/portfolio ideas (see CONTRIBUTING).

**Quick Start:**

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

---

## License

MIT License - Free to use, modify, and distribute. See [LICENSE](LICENSE) for details.

## Author

**lawaloy** - [GitHub](https://github.com/lawaloy)

---

## API Architecture Details

Our API client (`src/api_client.py`) provides:

- **Thread-safe rate limiting**: Token bucket algorithm ensures we never exceed 60 calls/min
- **Automatic retry**: Exponential backoff on failures (1s, 2s, 4s)
- **429 handling**: Respects Retry-After headers, resets rate limiter after waits
- **Session management**: Connection pooling for efficiency
- **Two modes**:
  - `get_stock_data_for_screening()`: 1 API call (quote only) - used for screening
  - `get_stock_data()`: 2 API calls (quote + profile) - used for qualified stocks

This architecture minimizes API calls while maximizing data quality.

---

## API Resources

- **Finnhub Documentation**: <https://finnhub.io/docs/api>
- **API Status**: <https://finnhub.io/status>
- **Support**: <support@finnhub.io>
- **Dashboard**: <https://finnhub.io/dashboard> (monitor your usage)

---

## Do you need any help?

- Check `logs/stock_tracker_errors_*.log` for error details
- Review the Troubleshooting section above
- Open an issue on GitHub with log excerpts
- Check Finnhub API status if data fetch fails
