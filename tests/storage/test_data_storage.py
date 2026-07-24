"""Tests for storage module."""

import unittest
import unittest.mock
import tempfile
import shutil
from pathlib import Path
import pandas as pd
import json
from datetime import date

from src.storage.data_storage import DataStorage


class TestDataStorage(unittest.TestCase):
    """Test cases for data storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.storage = DataStorage(data_dir=self.test_data_dir)
        self.sample_df = pd.DataFrame({
            'symbol': ['AAPL', 'GOOGL'],
            'close': [150.0, 2800.0],
            'volume': [50000000, 30000000]
        })
        self.sample_summary = {
            'total_stocks': 2,
            'date': str(date.today())
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_data_dir, ignore_errors=True)

    def test_storage_initialization(self):
        """Test that storage initializes correctly."""
        self.assertIsInstance(self.storage, DataStorage)
        self.assertTrue(Path(self.test_data_dir).exists())

    def test_save_daily_data(self):
        """Test saving daily data to CSV."""
        data_list = self.sample_df.to_dict('records')
        self.storage.save_daily_data(data_list)
        csv_files = list(Path(self.test_data_dir).glob("daily_data_*.csv"))
        self.assertEqual(len(csv_files), 1)

    def test_save_summary(self):
        """Test saving summary to JSON."""
        self.storage.save_summary(self.sample_summary)
        json_files = list(Path(self.test_data_dir).glob("summary_*.json"))
        self.assertEqual(len(json_files), 1)

    def test_load_daily_data(self):
        """Test loading daily data from CSV."""
        data_list = self.sample_df.to_dict('records')
        self.storage.save_daily_data(data_list)
        loaded_df = self.storage.load_daily_data()
        self.assertIsInstance(loaded_df, pd.DataFrame)
        self.assertEqual(len(loaded_df), 2)
        self.assertIn('symbol', loaded_df.columns)

    def test_load_summary(self):
        """Test loading summary from JSON."""
        self.storage.save_summary(self.sample_summary)
        json_files = list(Path(self.test_data_dir).glob("summary_*.json"))
        self.assertEqual(len(json_files), 1)
        with open(json_files[0], 'r') as f:
            loaded_summary = json.load(f)
        self.assertIsInstance(loaded_summary, dict)
        self.assertEqual(loaded_summary['total_stocks'], 2)

    def test_save_projections_writes_ordered_csv_and_markdown(self):
        """Projection CSV keeps the stable column order and still emits markdown."""
        projections = {
            "AAPL": {
                "symbol": "AAPL",
                "name": "Apple",
                "current_price": 180.0,
                "target_low": 175.0,
                "target_mid": 185.0,
                "target_high": 195.0,
                "expected_change_percent": 2.5,
                "recommendation": "BUY",
                "confidence": 80,
                "trend": "up",
                "momentum_score": 0.6,
                "volatility_score": 0.2,
                "risk_level": "medium",
                "reason": "momentum",
                "projection_date": "2026-05-25",
                "generated_at": "2026-05-20T12:00:00",
                "extra_ignored": True,
            }
        }

        csv_path = Path(self.storage.save_projections(projections, date=date(2026, 5, 20)))
        self.assertTrue(csv_path.exists())
        df = pd.read_csv(csv_path)
        self.assertEqual(
            list(df.columns),
            [
                "symbol",
                "name",
                "current_price",
                "target_low",
                "target_mid",
                "target_high",
                "expected_change_percent",
                "recommendation",
                "confidence",
                "trend",
                "momentum_score",
                "volatility_score",
                "risk_level",
                "reason",
                "projection_date",
                "generated_at",
            ],
        )
        self.assertEqual(df.iloc[0]["symbol"], "AAPL")
        md_path = csv_path.with_suffix(".md")
        self.assertTrue(md_path.exists())
        self.assertIn("Stock Market Projections Report", md_path.read_text(encoding="utf-8"))

    def test_save_projections_still_returns_csv_when_markdown_fails(self):
        """Markdown report failures must not block the projections CSV path."""
        projections = {
            "AAPL": {
                "symbol": "AAPL",
                "current_price": 180.0,
                "expected_change_percent": 1.0,
                "recommendation": "HOLD",
                "confidence": 50,
                "trend": "flat",
            }
        }

        with unittest.mock.patch.object(
            DataStorage,
            "_generate_projection_markdown",
            side_effect=RuntimeError("markdown boom"),
        ):
            csv_path = Path(
                self.storage.save_projections(projections, date=date(2026, 5, 21))
            )

        self.assertTrue(csv_path.exists())
        self.assertFalse(csv_path.with_suffix(".md").exists())
        self.assertEqual(pd.read_csv(csv_path).iloc[0]["symbol"], "AAPL")

    def test_save_projections_empty_returns_none(self):
        self.assertIsNone(self.storage.save_projections({}))


if __name__ == '__main__':
    unittest.main()
