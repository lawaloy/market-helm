# Architecture

Overview of the codebase, daily workflow, and Finnhub API usage.

---

## Project structure

```text
market-helm/
├── main.py                     # Entry point (run this!)
├── src/
│   ├── __init__.py
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

The dashboard lives under `dashboard/` (FastAPI backend + React frontend). See [dashboard/README.md](../dashboard/README.md).

---

## How the daily workflow works

1. **Index fetching** — stock symbols from S&P 500 (first 100) and NASDAQ-100.
2. **Screening** (1 API call per stock) — quick price/volume check to filter candidates.
3. **Data fetching** (2 API calls per qualified stock) — detailed data for the top N stocks.
4. **Analysis** — calculate changes, identify trends, optional AI summary.
5. **Storage** — save CSV/JSON under `data/` (or `DATA_DIR`).

---

## Rate limiting

- **Free tier:** 60 API calls per minute.
- **Typical run:** ~241 total calls (~4 minutes).
- **How we stay under the limit:**
  - Screening uses a lightweight 1-call method (quote only).
  - Only qualified stocks get the full 2-call fetch (quote + profile).
  - S&P 500 is capped at 100 symbols for screening.
  - 2 parallel workers with staggered starts.
  - Automatic pauses every 25–50 requests.

---

## API client

Implementation: `src/services/api_client.py`.

| Capability | Detail |
|------------|--------|
| **Rate limiting** | Thread-safe token bucket; stays under 60 calls/min |
| **Retry** | Exponential backoff on failures (1s, 2s, 4s) |
| **429 handling** | Respects `Retry-After`; resets limiter after waits |
| **Session** | Connection pooling |

**Two fetch modes:**

- `get_stock_data_for_screening()` — 1 API call (quote only), used during screening.
- `get_stock_data()` — 2 API calls (quote + profile), used for qualified stocks.

This minimizes API usage while keeping data quality for the final set.

---

## External resources

- **Finnhub documentation:** <https://finnhub.io/docs/api>
- **API status:** <https://finnhub.io/status>
- **Support:** <support@finnhub.io>
- **Usage dashboard:** <https://finnhub.io/dashboard>

---

## Related

- [CONFIGURATION.md](CONFIGURATION.md) — tune indices and filters
- [ADVANCED.md](ADVANCED.md) — OpenAI summaries, custom providers
- [STOCK_PROJECTIONS.md](STOCK_PROJECTIONS.md) — projection pipeline
