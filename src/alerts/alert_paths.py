"""Resolve alert config locations for repo dev vs pip install (~/.market-helm)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def user_config_dir() -> Path:
    """Per-user config directory (same location as the dashboard uses)."""
    home = Path.home()
    legacy = home / ".market-desk"
    dest = home / ".market-helm"
    if not dest.exists() and legacy.exists():
        try:
            legacy.rename(dest)
        except OSError:
            pass
    return dest


def bundled_example_path() -> Path:
    return _REPO_ROOT / "config" / "alerts.example.json"


def resolve_alerts_config_path(explicit: Optional[Path] = None) -> Path:
    """Path to alerts.json: env override, then user file, then repo dev file."""
    if explicit is not None:
        return Path(explicit)
    env_path = os.environ.get("MARKET_HELM_ALERTS_CONFIG")
    if env_path:
        return Path(env_path)
    user_path = user_config_dir() / "alerts.json"
    if user_path.exists():
        return user_path
    repo_path = _REPO_ROOT / "config" / "alerts.json"
    if repo_path.exists():
        return repo_path
    return user_path


def init_user_alerts_config(force: bool = False) -> Path:
    """Copy bundled alerts.example.json to ~/.market-helm/alerts.json."""
    dest = user_config_dir() / "alerts.json"
    user_config_dir().mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        raise FileExistsError(str(dest))
    example = bundled_example_path()
    if not example.exists():
        raise FileNotFoundError(f"Bundled example not found: {example}")
    shutil.copy(example, dest)
    return dest
