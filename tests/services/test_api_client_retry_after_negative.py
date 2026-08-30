"""Negative Retry-After values must clamp to 60 seconds before sleep."""

import unittest
from unittest.mock import Mock, patch

from src.services.api_client import FinnhubClient


class TestRetryAfterNegative(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key_12345"

    @patch("src.services.api_client.time.sleep")
    @patch("requests.Session")
    def test_negative_retry_after_defaults_to_sixty(self, mock_session, mock_sleep):
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "-1"}

        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = {"c": 150.0}
        ok.raise_for_status = Mock()

        session = Mock()
        session.get.side_effect = [limited, ok]
        mock_session.return_value = session

        client = FinnhubClient(api_key=self.api_key)
        client.session = session
        client.rate_limiter.wait_if_needed = Mock()

        self.assertEqual(client._make_request("quote", {"symbol": "AAPL"}), {"c": 150.0})
        mock_sleep.assert_called_once_with(60)


if __name__ == "__main__":
    unittest.main()
