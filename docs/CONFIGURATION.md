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

## Related

- [USAGE.md](USAGE.md) — how to run the tracker
- [ARCHITECTURE.md](ARCHITECTURE.md) — how screening and rate limiting work
