"""Tests for core logging module."""

import unittest
import logging
import tempfile
import shutil
from pathlib import Path

from src.core.logger import setup_logger


class TestCoreLogger(unittest.TestCase):
    """Test cases for logger configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_log_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_log_dir, ignore_errors=True)

    def test_logger_creation(self):
        """Test that logger is created successfully."""
        logger = setup_logger(log_dir=self.test_log_dir)
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.DEBUG)

    def test_logger_has_handlers(self):
        """Test that logger has console and file handlers."""
        logger = setup_logger(log_dir=self.test_log_dir)
        self.assertGreaterEqual(len(logger.handlers), 3)

    def test_log_files_created(self):
        """Test that log files are created."""
        logger = setup_logger(log_dir=self.test_log_dir)
        logger.info("Test message")
        log_files = list(Path(self.test_log_dir).glob("*.log"))
        self.assertGreaterEqual(len(log_files), 2)

    def test_logger_reuse(self):
        """Test that calling setup_logger twice returns same logger."""
        logger1 = setup_logger(name="test_logger", log_dir=self.test_log_dir)
        logger2 = setup_logger(name="test_logger", log_dir=self.test_log_dir)
        self.assertEqual(logger1.name, logger2.name)

    def test_renames_legacy_stock_tracker_log_files(self):
        """Legacy stock_tracker_*.log files are renamed to market_helm_*.log."""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path(self.test_log_dir)
        legacy = log_dir / f"stock_tracker_{today}.log"
        legacy_err = log_dir / f"stock_tracker_errors_{today}.log"
        legacy.write_text("old main\n", encoding="utf-8")
        legacy_err.write_text("old err\n", encoding="utf-8")

        setup_logger(log_dir=self.test_log_dir)

        self.assertFalse(legacy.exists())
        self.assertFalse(legacy_err.exists())
        self.assertTrue((log_dir / f"market_helm_{today}.log").exists())
        self.assertTrue((log_dir / f"market_helm_errors_{today}.log").exists())
        self.assertIn("old main", (log_dir / f"market_helm_{today}.log").read_text(encoding="utf-8"))

    def test_skips_legacy_rename_when_destination_already_exists(self):
        """Existing market_helm_*.log must not be overwritten by legacy rename."""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path(self.test_log_dir)
        legacy = log_dir / f"stock_tracker_{today}.log"
        dest = log_dir / f"market_helm_{today}.log"
        legacy.write_text("legacy only\n", encoding="utf-8")
        dest.write_text("already migrated\n", encoding="utf-8")

        logger = setup_logger(log_dir=self.test_log_dir)

        self.assertTrue(legacy.exists())
        self.assertEqual(dest.read_text(encoding="utf-8"), "already migrated\n")
        self.assertIsInstance(logger, logging.Logger)

    def test_soft_fails_when_legacy_rename_raises_oserror(self):
        """Boot must still return a usable logger if legacy rename races."""
        from datetime import datetime
        from unittest.mock import patch

        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path(self.test_log_dir)
        legacy = log_dir / f"stock_tracker_{today}.log"
        legacy.write_text("legacy\n", encoding="utf-8")

        with patch.object(Path, "rename", side_effect=OSError("busy")):
            logger = setup_logger(name="logger_rename_soft_fail", log_dir=self.test_log_dir)

        self.assertIsInstance(logger, logging.Logger)
        self.assertGreaterEqual(len(logger.handlers), 3)
        self.assertTrue(legacy.exists())


if __name__ == '__main__':
    unittest.main()
