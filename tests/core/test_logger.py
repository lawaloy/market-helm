"""Tests for core logging module."""

import logging
import shutil
import tempfile
import unittest
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

    def test_soft_fails_when_log_dir_mkdir_raises_oserror(self):
        """Unwritable log dir must not abort imports that call setup_logger."""
        from unittest.mock import patch

        with patch.object(Path, "mkdir", side_effect=OSError("read-only")):
            logger = setup_logger(name="logger_mkdir_soft_fail", log_dir="/unwritable/logs")

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)
        logger.info("console-only still works")

    def test_soft_fails_when_file_handler_raises_oserror(self):
        """Disk-full / permissioned FileHandler must keep console logging."""
        from unittest.mock import patch

        with patch(
            "src.core.logger.logging.FileHandler",
            side_effect=OSError("disk full"),
        ):
            logger = setup_logger(name="logger_filehandler_soft_fail", log_dir=self.test_log_dir)

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)


if __name__ == "__main__":
    unittest.main()
