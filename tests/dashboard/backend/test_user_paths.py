"""Tests for dashboard.backend.user_paths legacy migration."""

import sys
from pathlib import Path

import pytest


def _fake_home(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    if sys.platform == "win32":
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_user_config_dir_no_migration_when_market_helm_exists(monkeypatch, tmp_path):
    home = _fake_home(monkeypatch, tmp_path)
    dest = home / ".market-helm"
    dest.mkdir()
    (dest / "x.txt").write_text("ok")

    from dashboard.backend import user_paths

    assert user_paths.user_config_dir() == dest
    assert (dest / "x.txt").read_text() == "ok"


def test_user_config_dir_migrates_market_desk(monkeypatch, tmp_path):
    home = _fake_home(monkeypatch, tmp_path)
    md = home / ".market-desk"
    md.mkdir()
    (md / "data").mkdir()
    (md / "data" / "daily.csv").write_text("sym")

    from dashboard.backend import user_paths

    d = user_paths.user_config_dir()
    assert d == home / ".market-helm"
    assert d.exists()
    assert not md.exists()
    assert (d / "data" / "daily.csv").read_text() == "sym"


def test_user_config_dir_soft_fails_when_legacy_rename_raises(monkeypatch, tmp_path):
    home = _fake_home(monkeypatch, tmp_path)
    md = home / ".market-desk"
    md.mkdir()
    (md / "keep.txt").write_text("legacy")

    from dashboard.backend import user_paths

    def boom(_self, _dest):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "rename", boom)

    d = user_paths.user_config_dir()
    assert d == home / ".market-helm"
    assert not d.exists()
    assert md.exists()
    assert (md / "keep.txt").read_text() == "legacy"
