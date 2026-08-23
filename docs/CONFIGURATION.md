# Configuration

Edit JSON files under `config/` to control which stocks are screened and how they are filtered.

---

## Indices to track

Edit `config/exchanges.json`:

```json
{
  "indices_to_track": [
    "S&P 500",
    "NASDAQ-100"
  ]
}
```

---

## Screening filters

Edit `config/filters.json`:

```json
{
  "volume_threshold": 1000000,
  "price_min": 5.0,
  "price_max": 500.0,
  "min_daily_change_pct": 2.0,
  "market_cap_min": 1000000000,
  "top_n": 30
}
```

| Field | Purpose |
|-------|---------|
| `volume_threshold` | Minimum daily volume |
| `price_min` / `price_max` | Acceptable price range |
| `min_daily_change_pct` | Minimum % move (filters quiet stocks) |
| `market_cap_min` | Minimum market cap (e.g. $1B) |
| `top_n` | How many stocks to track after screening |

**Tip:** Lower `top_n` to run faster (default effective target is ~20 for ~4 minute runs on the free tier).

---

## Performance tips

### Run faster

- **Lower `top_n`** — currently optimized around 20.
- **Track fewer indices** — remove one from `config/exchanges.json`.
- **Upgrade API tier** — paid Finnhub plans allow more calls per minute.

### Run cheaper

- Stay on the free tier (60 calls/min).
- Run once per day when using a scheduler.
- Use Docker for a consistent, lightweight deployment — see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Optional AI summaries

Without `OPENAI_API_KEY`, MarketHelm generates a template-based summary. To use
the optional OpenAI summarizer:

1. Install the AI extra:

   ```bash
   pip install 'market-helm[ai]'
   ```

2. Add the key to `.env` or the process environment:

   ```text
   FINNHUB_API_KEY=your-finnhub-key
   OPENAI_API_KEY=your-openai-key
   ```

3. Run the tracker normally. The summarizer falls back safely when the optional
   package or API call is unavailable.

The current model and prompt are defined in `src/analysis/ai_summarizer.py`.
Review provider pricing and model availability before enabling this in a scheduled
or hosted environment.

---

## Custom market-data providers

The Finnhub boundary lives in `src/services/api_client.py`. A replacement provider
should preserve the existing client contract or be introduced behind an adapter so
screening and workflow code do not become provider-specific. It must also define
authentication, quotas, retry behavior, response normalization, and tests.

---

## Related

- [USAGE.md](USAGE.md) — how to run the tracker
- [ARCHITECTURE.md](ARCHITECTURE.md) — how screening and rate limiting work
- [DEPLOYMENT.md](DEPLOYMENT.md) — production environment and secrets
