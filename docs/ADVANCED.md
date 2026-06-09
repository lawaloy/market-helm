# Advanced topics

Optional features and customization beyond the default daily tracker.

---

## AI-powered market summaries (optional)

By default, the tool generates basic market summaries from templates. Add OpenAI for natural-language summaries.

**With OpenAI:**

```text
Market Summary for YYYY-MM-DD:

Today's market showed strong momentum with technology stocks leading the charge.
The top gainer, Micron Technology (MU), surged 10.51% on strong earnings expectations,
while semiconductor stocks broadly outperformed...
```

**Without OpenAI (demo mode):**

```text
Market Summary for YYYY-MM-DD:
Top gainer: MU +10.51%
Top loser: PLTR -5.56%
Overall market: Mixed with 23 gainers and 7 losers
```

### Setup

1. **Get an OpenAI API key** (~$0.01–0.05 per summary):
   - Sign up: <https://platform.openai.com/signup>
   - Create a key: <https://platform.openai.com/api-keys>

2. **Add to `.env`:**

   ```text
   FINNHUB_API_KEY=your-finnhub-key
   OPENAI_API_KEY=sk-proj-your-openai-key-here
   ```

3. **Install the optional extra** (if not already):

   ```bash
   pip install 'market-helm[ai]'
   ```

4. **Run normally** — AI summaries are automatic when the key is present.

**Cost estimate:** ~$0.02/day for GPT-4 summaries (< $1/month for daily runs).

---

## Custom data providers

To use a different market data provider, extend or replace calls in `src/services/api_client.py` with your provider's API.

Keep rate limiting and retry behavior consistent with your provider's limits.

---

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — API client design
- [CONFIGURATION.md](CONFIGURATION.md) — tuning run speed and cost
