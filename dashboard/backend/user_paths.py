"""User-level config/data locations when installed from a wheel."""

from __future__ import annotations

from pathlib import Path

from src.core.compat import resolve_user_config_dir


def user_config_dir() -> Path:
    """Directory for app config and data: ~/.markethelm when installed from a wheel.

    On first use, if that folder does not exist but ``~/.market-helm`` (or the older
    ``~/.market-desk``) does, it is renamed to ``~/.markethelm`` automatically. If the rename
    fails the legacy folder keeps being used.
    """
    return resolve_user_config_dir(Path.home())
