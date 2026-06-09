# Troubleshooting & FAQ

---

## Common issues

### API key required

- Ensure a `.env` file exists with `FINNHUB_API_KEY=your-key`.
- Check the key is correct (40 characters).
- Restart your terminal after creating `.env`.

### Rate limit exceeded (429)

- The tool has built-in retry logic.
- If it happens frequently:
  - Lower `top_n` in `config/filters.json` — see [CONFIGURATION.md](CONFIGURATION.md).
  - Wait 5–10 minutes between runs.
  - Consider upgrading to a paid Finnhub tier.

### No data fetched

- Check your internet connection.
- Verify the Finnhub API key is valid.
- Check `logs/market_helm_errors_*.log` for details.
- Check [Finnhub API status](https://finnhub.io/status).

### Logs not showing

- Logs are in the `logs/` folder (created automatically).
- Console shows INFO level; files show DEBUG level.

---

## FAQ

**Is this free?**  
Yes. Finnhub's free tier is sufficient for daily tracking.

**Can I track other stocks?**  
Yes. Edit `config/exchanges.json` to add symbols or change indices — see [CONFIGURATION.md](CONFIGURATION.md).

**What if I miss a day?**  
Rerun the tracker. Each run is independent; data is saved with the date.

**Can I backtest strategies?**  
This tool focuses on daily snapshots. Backtesting would require historical data (not included).

**Is my data private?**  
Yes. Data stays on your machine. API keys never leave your environment.

---

## Getting help

- Check `logs/market_helm_errors_*.log` for error details.
- Open a [GitHub issue](https://github.com/lawaloy/market-helm/issues) with log excerpts.
- Review [USAGE.md](USAGE.md) and [DEPLOYMENT.md](DEPLOYMENT.md) for setup questions.
