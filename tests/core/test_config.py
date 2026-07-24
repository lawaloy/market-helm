"""Tests for core configuration module."""

import unittest
from unittest.mock import patch, mock_open

from src.core.config import get_indices_to_track, _DEFAULT_INDICES


class TestCoreConfig(unittest.TestCase):
    """Test cases for configuration loading."""

    def test_default_indices(self):
        """Test that default indices are defined."""
        self.assertIsInstance(_DEFAULT_INDICES, list)
        self.assertGreater(len(_DEFAULT_INDICES), 0)
        self.assertIn("S&P 500", _DEFAULT_INDICES)

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"indices_to_track": ["S&P 500", "NASDAQ-100", "Dow 30"]}')
    def test_load_from_config_file(self, mock_file, mock_exists):
        """Test loading indices from config file."""
        mock_exists.return_value = True
        indices = get_indices_to_track()
        self.assertIsInstance(indices, list)
        self.assertIn("S&P 500", indices)

    @patch('pathlib.Path.exists')
    def test_fallback_to_defaults(self, mock_exists):
        """Test fallback to default indices when config not found."""
        mock_exists.return_value = False
        indices = get_indices_to_track()
        self.assertEqual(indices, _DEFAULT_INDICES)

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"indices_to_track": []}')
    def test_empty_config_uses_defaults(self, mock_file, mock_exists):
        """Test that empty config falls back to defaults."""
        mock_exists.return_value = True
        indices = get_indices_to_track()
        self.assertEqual(indices, _DEFAULT_INDICES)

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{not-json')
    def test_corrupt_config_uses_defaults(self, mock_file, mock_exists):
        """Corrupt exchanges.json must not crash fetch/tracker boot."""
        mock_exists.return_value = True
        indices = get_indices_to_track()
        self.assertEqual(indices, _DEFAULT_INDICES)


if __name__ == '__main__':
    unittest.main()
