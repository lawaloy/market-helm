"""Tests for services API client module."""

import unittest
from unittest.mock import Mock, patch

import requests

from src.services.api_client import RateLimiter, FinnhubClient


class TestRateLimiter(unittest.TestCase):
    """Test cases for rate limiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter(calls_per_minute=60)
        self.assertEqual(limiter.calls_per_minute, 60)
        self.assertGreater(limiter.tokens, 0)

    def test_wait_if_needed(self):
        """Test that wait_if_needed executes without error."""
        limiter = RateLimiter(calls_per_minute=60)
        limiter.wait_if_needed()
        self.assertLess(limiter.tokens, 10)


class TestFinnhubClient(unittest.TestCase):
    """Test cases for Finnhub API client."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345"

    def _client_with_session(self, session):
        with patch("requests.Session", return_value=session):
            client = FinnhubClient(api_key=self.api_key)
        client.session = session
        client.rate_limiter.wait_if_needed = lambda: None
        return client

    def test_client_requires_api_key(self):
        """Test that client raises error without API key."""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError) as context:
                FinnhubClient(api_key=None)
            self.assertIn("API key required", str(context.exception))

    @patch('requests.Session')
    def test_client_initialization(self, mock_session):
        """Test that client initializes with API key."""
        client = FinnhubClient(api_key=self.api_key)
        self.assertEqual(client.api_key, self.api_key)
        self.assertEqual(client.base_url, "https://finnhub.io/api/v1")

    @patch('requests.Session')
    def test_get_quote_structure(self, mock_session):
        """Test get_quote returns expected structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "c": 150.0, "h": 152.0, "l": 149.0, "o": 151.0,
            "pc": 148.0, "t": 1234567890
        }
        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        client = FinnhubClient(api_key=self.api_key)
        client.session = mock_session_instance
        quote = client.get_quote("AAPL")

        self.assertIsInstance(quote, dict)
        self.assertIn("c", quote)
        self.assertIn("pc", quote)

    @patch('requests.Session')
    def test_get_stock_data_for_screening(self, mock_session):
        """Test lightweight screening data fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "c": 150.0, "pc": 148.0, "v": 50000000
        }
        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        client = FinnhubClient(api_key=self.api_key)
        client.session = mock_session_instance
        data = client.get_stock_data_for_screening("AAPL")

        self.assertIsNotNone(data)
        self.assertEqual(data["symbol"], "AAPL")
        self.assertIn("close", data)
        self.assertIn("volume", data)
        self.assertIn("change_percent", data)

    @patch("src.services.api_client.time.sleep", return_value=None)
    def test_make_request_retries_429_then_succeeds(self, _sleep):
        """429 responses honor Retry-After, reset tokens, and retry."""
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "2"}
        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = {"c": 10.0}
        ok.raise_for_status = Mock()
        session = Mock()
        session.get.side_effect = [limited, ok]
        client = self._client_with_session(session)
        client.rate_limiter.tokens = 0

        data = client._make_request("quote", {"symbol": "AAPL"})

        self.assertEqual(data, {"c": 10.0})
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(client.rate_limiter.tokens, client.rate_limiter.calls_per_minute)

    @patch("src.services.api_client.time.sleep", return_value=None)
    def test_make_request_exhausts_429_retries(self, _sleep):
        """Persistent 429 after max attempts raises HTTPError."""
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "1"}
        session = Mock()
        session.get.return_value = limited
        client = self._client_with_session(session)

        with self.assertRaises(requests.exceptions.HTTPError) as ctx:
            client._make_request("quote", {"symbol": "AAPL"})

        self.assertIn("Rate limit exceeded", str(ctx.exception))
        self.assertEqual(session.get.call_count, 3)

    def test_make_request_raises_on_finnhub_error_payload(self):
        """Finnhub JSON error bodies become ValueError."""
        response = Mock()
        response.status_code = 200
        response.raise_for_status = Mock()
        response.json.return_value = {"error": "Invalid API key"}
        session = Mock()
        session.get.return_value = response
        client = self._client_with_session(session)

        with self.assertRaises(ValueError) as ctx:
            client._make_request("quote", {"symbol": "AAPL"})

        self.assertIn("Invalid API key", str(ctx.exception))

    @patch("src.services.api_client.time.sleep", return_value=None)
    def test_make_request_retries_transient_request_errors(self, _sleep):
        """Transient RequestException retries then re-raises."""
        session = Mock()
        session.get.side_effect = [
            requests.exceptions.ConnectionError("boom"),
            requests.exceptions.ConnectionError("boom"),
            requests.exceptions.ConnectionError("boom"),
        ]
        client = self._client_with_session(session)

        with self.assertRaises(requests.exceptions.ConnectionError):
            client._make_request("quote", {"symbol": "AAPL"})

        self.assertEqual(session.get.call_count, 3)

    def test_get_company_profile_uses_fresh_cache(self):
        """Fresh profile cache hits skip a second Finnhub call."""
        session = Mock()
        client = self._client_with_session(session)
        client._profile_cache["AAPL"] = ({"name": "Apple Inc"}, 1_700_000_000.0)

        with patch("src.services.api_client.time.time", return_value=1_700_000_100.0):
            with patch.object(client, "_make_request") as make_request:
                profile = client.get_company_profile("aapl")

        self.assertEqual(profile["name"], "Apple Inc")
        make_request.assert_not_called()

    def test_get_stock_data_returns_none_when_quote_missing_price(self):
        """Missing current price soft-fails to None instead of crashing."""
        session = Mock()
        client = self._client_with_session(session)

        with patch.object(client, "get_quote", return_value={"c": None, "pc": 100}):
            self.assertIsNone(client.get_stock_data("AAPL"))

    def test_get_stock_data_zero_previous_close_avoids_division(self):
        """pc=0 yields 0.0 change_percent without ZeroDivisionError."""
        session = Mock()
        client = self._client_with_session(session)

        with patch.object(
            client,
            "get_quote",
            return_value={"c": 12.0, "pc": 0, "o": 11, "h": 13, "l": 10, "v": 1},
        ):
            with patch.object(client, "get_company_profile", return_value={"name": "X"}):
                data = client.get_stock_data("ZZZ")

        self.assertIsNotNone(data)
        self.assertEqual(data["change_percent"], 0.0)
        self.assertEqual(data["name"], "X")

    def test_get_stock_data_profile_failure_falls_back_to_symbol_name(self):
        """Profile fetch errors keep the quote and fall back to the ticker."""
        session = Mock()
        client = self._client_with_session(session)

        with patch.object(
            client,
            "get_quote",
            return_value={"c": 50.0, "pc": 49.0, "o": 49, "h": 51, "l": 48, "v": 10},
        ):
            with patch.object(
                client, "get_company_profile", side_effect=RuntimeError("profile down")
            ):
                data = client.get_stock_data("MSFT")

        self.assertEqual(data["name"], "MSFT")
        self.assertEqual(data["exchange"], "Unknown")

    def test_get_stock_data_skips_profile_when_disabled(self):
        """include_profile=False never calls Finnhub profile2."""
        session = Mock()
        client = self._client_with_session(session)

        with patch.object(
            client,
            "get_quote",
            return_value={"c": 50.0, "pc": 49.0, "o": 49, "h": 51, "l": 48, "v": 10},
        ):
            with patch.object(client, "get_company_profile") as get_profile:
                data = client.get_stock_data("MSFT", include_profile=False)

        get_profile.assert_not_called()
        self.assertEqual(data["name"], "MSFT")

    def test_batch_get_stock_data_maps_failures_to_none(self):
        """Per-symbol failures stay isolated as None entries."""
        session = Mock()
        client = self._client_with_session(session)

        with patch.object(
            client,
            "get_stock_data",
            side_effect=[{"symbol": "AAPL"}, None],
        ) as get_stock_data:
            results = client.batch_get_stock_data(["AAPL", "BAD"], include_profile=False)

        self.assertEqual(results["AAPL"]["symbol"], "AAPL")
        self.assertIsNone(results["BAD"])
        self.assertEqual(get_stock_data.call_count, 2)


if __name__ == '__main__':
    unittest.main()
