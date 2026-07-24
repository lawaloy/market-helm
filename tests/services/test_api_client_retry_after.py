"""Tests for Finnhub Retry-After header parsing."""

import unittest
from unittest.mock import Mock, patch

from src.services.api_client import FinnhubClient


class TestRetryAfterParsing(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key_12345"

    @patch("src.services.api_client.time.sleep")
    @patch("requests.Session")
    def test_non_integer_retry_after_defaults_and_retries(self, mock_session, mock_sleep):
        """HTTP-date / garbage Retry-After must not raise ValueError mid-fetch."""
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}

        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = {"c": 150.0, "pc": 148.0}
        ok.raise_for_status = Mock()

        session = Mock()
        session.get.side_effect = [limited, ok]
        mock_session.return_value = session

        client = FinnhubClient(api_key=self.api_key)
        client.session = session
        client.rate_limiter.wait_if_needed = Mock()

        data = client._make_request("quote", {"symbol": "AAPL"})

        self.assertEqual(data["c"], 150.0)
        mock_sleep.assert_called_once_with(60)

    @patch("src.services.api_client.time.sleep")
    @patch("requests.Session")
    def test_garbage_retry_after_defaults_to_sixty(self, mock_session, mock_sleep):
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "abc"}

        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = {"ok": True}
        ok.raise_for_status = Mock()

        session = Mock()
        session.get.side_effect = [limited, ok]
        mock_session.return_value = session

        client = FinnhubClient(api_key=self.api_key)
        client.session = session
        client.rate_limiter.wait_if_needed = Mock()

        self.assertEqual(client._make_request("quote", {"symbol": "AAPL"}), {"ok": True})
        mock_sleep.assert_called_once_with(60)


if __name__ == "__main__":
    unittest.main()
