"""Expired Finnhub profile cache entries must refetch instead of serving forever.

``test_get_company_profile_uses_fresh_cache`` only locks the in-TTL hit path.
A regression that dropped the TTL comparison would keep the first profile for
the process lifetime and skip ``stock/profile2`` after the 24h window.
"""

from unittest.mock import Mock, patch

from src.services.api_client import FinnhubClient


def _client() -> FinnhubClient:
    session = Mock()
    with patch("requests.Session", return_value=session):
        client = FinnhubClient(api_key="test_api_key_12345")
    client.session = session
    client.rate_limiter.wait_if_needed = lambda: None
    return client


def test_get_company_profile_refetches_when_ttl_expires() -> None:
    client = _client()
    stale = {"name": "Stale Apple"}
    fresh = {"name": "Apple Inc", "exchange": "NASDAQ"}
    cached_at = 1_700_000_000.0
    client._profile_cache["AAPL"] = (stale, cached_at)

    # Comparison is strict ``< ttl``, so an entry exactly 24h old is expired.
    now = cached_at + client._profile_cache_ttl
    with patch("src.services.api_client.time.time", return_value=now):
        with patch.object(client, "_make_request", return_value=fresh) as make_request:
            profile = client.get_company_profile("aapl")

    assert profile == fresh
    make_request.assert_called_once_with("stock/profile2", {"symbol": "aapl"})
    assert client._profile_cache["AAPL"] == (fresh, now)


def test_get_company_profile_fetches_on_cache_miss() -> None:
    client = _client()
    fresh = {"name": "Microsoft", "exchange": "NASDAQ"}
    now = 1_700_000_000.0

    with patch("src.services.api_client.time.time", return_value=now):
        with patch.object(client, "_make_request", return_value=fresh) as make_request:
            profile = client.get_company_profile("MSFT")

    assert profile == fresh
    make_request.assert_called_once_with("stock/profile2", {"symbol": "MSFT"})
    assert client._profile_cache["MSFT"] == (fresh, now)
