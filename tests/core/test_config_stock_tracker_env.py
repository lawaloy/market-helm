"""Tests for STOCK_TRACKER_CONFIG env override in get_indices_to_track."""

import json
from pathlib import Path

from src.core.config import _DEFAULT_INDICES, get_indices_to_track


def test_loads_indices_from_stock_tracker_config_env(monkeypatch, tmp_path):
    custom = tmp_path / "custom_exchanges.json"
    custom.write_text(
        json.dumps({"indices_to_track": ["Dow Jones", "NASDAQ-100"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STOCK_TRACKER_CONFIG", str(custom))

    def only_custom_exists(self: Path) -> bool:
        try:
            return self.resolve() == custom.resolve()
        except OSError:
            return False

    monkeypatch.setattr(Path, "exists", only_custom_exists)

    assert get_indices_to_track() == ["Dow Jones", "NASDAQ-100"]


def test_stock_tracker_config_env_overrides_bundled_exchanges_json(
    monkeypatch, tmp_path
):
    """Env path must win even when repo config/exchanges.json exists on disk."""
    custom = tmp_path / "custom_exchanges.json"
    custom.write_text(
        json.dumps({"indices_to_track": ["Dow Jones"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STOCK_TRACKER_CONFIG", str(custom))

    # Do not mock Path.exists — the bundled config is present in this checkout.
    assert get_indices_to_track() == ["Dow Jones"]


def test_invalid_stock_tracker_config_falls_back_to_bundled(monkeypatch, tmp_path):
    """Corrupt env config must not stick on defaults when bundled is readable."""
    bad = tmp_path / "bad_exchanges.json"
    bad.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("STOCK_TRACKER_CONFIG", str(bad))

    assert get_indices_to_track() == ["S&P 500", "NASDAQ-100"]


def test_defaults_when_stock_tracker_config_unset_and_paths_missing(monkeypatch):
    monkeypatch.delenv("STOCK_TRACKER_CONFIG", raising=False)
    monkeypatch.setattr(Path, "exists", lambda self: False)

    assert get_indices_to_track() == _DEFAULT_INDICES


def test_defaults_when_stock_tracker_config_points_at_directory(monkeypatch, tmp_path):
    """Directory paths exist() but open() fails — soft-fall to defaults."""
    cfg_dir = tmp_path / "config_dir"
    cfg_dir.mkdir()
    monkeypatch.setenv("STOCK_TRACKER_CONFIG", str(cfg_dir))

    def only_dir_exists(self: Path) -> bool:
        try:
            return self.resolve() == cfg_dir.resolve()
        except OSError:
            return False

    monkeypatch.setattr(Path, "exists", only_dir_exists)

    assert get_indices_to_track() == _DEFAULT_INDICES
