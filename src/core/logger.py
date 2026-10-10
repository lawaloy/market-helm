"""
MarketHelm - Logging Configuration

Sets up logging with both console and file output, with different log levels.
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "markethelm", log_dir: str = "logs") -> logging.Logger:
    """
    Set up logger with console and file handlers.

    Args:
        name: Logger name
        log_dir: Directory to store log files

    Returns:
        Configured logger instance
    """
    # Create logger (console always works even if the log directory is unwritable).
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all levels

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")

    # Console handler - INFO level and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handlers are best-effort: a read-only container / permissioned volume
    # must not abort imports that call setup_logger at module load.
    log_path = Path(log_dir)
    try:
        log_path.mkdir(exist_ok=True)
    except OSError:
        return logger

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        file_handler = logging.FileHandler(log_path / f"markethelm_{today}.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass

    try:
        error_handler = logging.FileHandler(
            log_path / f"markethelm_errors_{today}.log", encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
    except OSError:
        pass

    return logger
