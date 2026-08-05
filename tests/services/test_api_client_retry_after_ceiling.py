"""Huge finite Retry-After values must clamp before sleep."""

import unittest
from unittest.mock import Mock, patch

from src.services.api_client import MAX_RETRY_AFTER_SECONDS, FinnhubClient


class TestRetryAfterCeiling(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key_12345"

    @patch("src.services.api_client.time.sleep")
    @patch("requests.Session")
    def test_huge_retry_after_is_clamped(self, mock_session, mock_sleep):
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "999999999"}

        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = {"c": 1.0}
        ok.raise_for_status = Mock()

        session = Mock()
        session.get.side_effect = [limited, ok]
        mock_session.return_value = session

        client = FinnhubClient(api_key=self.api_key)
        client.session = session
        client.rate_limiter.wait_if_needed = Mock()

        self.assertEqual(client._make_request("quote", {"symbol": "AAPL"}), {"c": 1.0})
        mock_sleep.assert_called_once_with(MAX_RETRY_AFTER_SECONDS)

    @patch("src.services.api_client.time.sleep")
    @patch("requests.Session")
    def test_retry_after_at_ceiling_is_unchanged(self, mock_session, mock_sleep):
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": str(MAX_RETRY_AFTER_SECONDS)}

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

        self.assertEqual(client._make_request("quote", {"symbol": "MSFT"}), {"ok": True})
        mock_sleep.assert_called_once_with(MAX_RETRY_AFTER_SECONDS)


if __name__ == "__main__":
    unittest.main()
