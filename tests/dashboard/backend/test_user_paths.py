"""Tests for dashboard.backend.user_paths."""

import sys
from pathlib import Path


def _fake_home(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    if sys.platform == "win32":
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_user_config_dir_is_dot_markethelm_in_home(monkeypatch, tmp_path):
    home = _fake_home(monkeypatch, tmp_path)

    from dashboard.backend import user_paths

    assert user_paths.user_config_dir() == home / ".markethelm"
