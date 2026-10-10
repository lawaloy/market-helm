"""User-level config/data locations when installed from a wheel."""

from __future__ import annotations

from pathlib import Path


def user_config_dir() -> Path:
    """Directory for app config and data: ~/.markethelm when installed from a wheel."""
    return Path.home() / ".markethelm"
