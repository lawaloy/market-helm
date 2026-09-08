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

### Projection backtesting

Evaluate saved projection files against closing prices on the exact fifth NYSE
trading session after each run:

```bash
market-helm backtest --data-dir data --days 365
market-helm backtest --data-dir data --days 365 --output data/backtest.json
```

The strict JSON report includes absolute error, directional accuracy, target-band
coverage, confidence calibration, confidence cohorts, recommendation cohorts,
and data-coverage counts. A projection is never rolled to a later close when its
exact target-session close is missing. Use `--horizon-sessions` or `--calendar`
to evaluate another explicit horizon, and `--all-samples` to include more than
the default 300 sample rows.

The repository also preserves a synthetic scenario baseline that detects changes
to evaluator semantics:

```bash
python3 scripts/projection_baseline.py check
```

Do not use its synthetic metrics to tune confidence; calibration requires a
representative baseline of real projections generated before their outcomes.

Newly fetched quote rows record the provider timestamp and Finnhub's explicit
previous-close value (`pc`) against its verified preceding XNYS session. This keeps
premarket, intraday, holiday, and weekend fetches from being mislabeled by the
snapshot filename. Legacy snapshots remain readable, but they cannot qualify as
calibration evidence and are excluded from observed-baseline metrics.
Weekend and holiday runs use their actual collection date, so they cannot replace
the preceding session's snapshot.

Assess the local forward archive against the documented minimum evidence gate:

```bash
python3 scripts/projection_baseline.py assess --data-dir data --days 365
```

The default gate requires at least 200 scored projections, 90% mature-outcome
coverage, 20 distinct run dates, 25 symbols, and two confidence cohorts with at
least 30 samples each. Every scored projection must have a timezone-aware
generation timestamp and every outcome must identify a verified previous-close
session. Thresholds are minimum evidence hygiene, not proof of model quality.

Once the assessment passes, preserve the exact report plus hashes of every input:

```bash
python3 scripts/projection_baseline.py capture --data-dir data --days 365 \
  --output-dir baselines/observed/projection-YYYY-MM-DD
```

Capture refuses to create an output directory when any qualification fails.
It evaluates a private copy of the input CSVs and hashes that same copy, preventing
a concurrent refresh from producing a report/manifest mismatch.

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

| File                              | Contents                                       |
| --------------------------------- | ---------------------------------------------- |
| `data/daily_data_YYYY-MM-DD.csv`  | Full stock data (prices, volume, changes)      |
| `data/summary_YYYY-MM-DD.json`    | Analysis summary (gainers, losers, statistics) |
| `logs/market_helm_YYYY-MM-DD.log` | Detailed execution logs                        |

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
