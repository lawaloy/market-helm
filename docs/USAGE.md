# Usage

How to run the daily tracker after [install](../README.md#quick-start-beginners-welcome).

---

## Entry points

### Option 1: CLI (recommended for daily use)

```bash
# Main entry point — formatted console output
python main.py
```

Or, after `pip install market-helm`:

```bash
market-helm
```

This runs the CLI interface which:

- Shows formatted console output
- Displays top gainers/losers
- Shows index performance
- Prints AI summary (if enabled)

### Option 2: Direct CLI module

```bash
python -m src.cli.commands
```

Same as Option 1, invoked as a module.

### Option 3: Direct workflow (programmatic)

```bash
python -m src.workflows.tracker
```

Runs the core workflow and returns structured JSON. Useful for:

- Testing workflow logic
- CI/CD pipelines
- Debugging without CLI formatting

### Option 4: Programmatic import

```python
from src.workflows.tracker import StockTrackerWorkflow

workflow = StockTrackerWorkflow()
result = workflow.run(use_screener=True)

if result["success"]:
    analysis = result["analysis"]
    top_gainers = analysis["top_gainers"]
    ai_summary = result.get("ai_summary")
```

Ideal for custom dashboards, scheduled tasks with custom notifications, or integration with other systems.

---

## Web dashboard

After install:

```bash
market-helm-web
```

Open **<http://localhost:8000>** — API docs at **/docs**.

For React development (Vite on port 3000, hot reload), see [dashboard/README.md](../dashboard/README.md#development-clone-hot-reload).

---

## Output files

Each run writes:

| File | Contents |
|------|----------|
| `data/daily_data_YYYY-MM-DD.csv` | Full stock data (prices, volume, changes) |
| `data/summary_YYYY-MM-DD.json` | Analysis summary (gainers, losers, statistics) |
| `logs/market_helm_YYYY-MM-DD.log` | Detailed execution logs |

Set `DATA_DIR` to change the output location — see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Console output

Example:

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

## Related

- [CONFIGURATION.md](CONFIGURATION.md) — indices and screening filters
- [DEPLOYMENT.md](DEPLOYMENT.md) — scheduling daily runs (cron, Docker, Kubernetes)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — errors and FAQ
