"""Tests for alert config path resolution."""

from pathlib import Path

from src.alerts.alert_paths import init_user_alerts_config, resolve_alerts_config_path


def test_resolve_prefers_explicit_path(tmp_path: Path) -> None:
    custom = tmp_path / "custom.json"
    custom.write_text('{"alerts": []}', encoding="utf-8")
    assert resolve_alerts_config_path(custom) == custom


def test_init_user_alerts_config_creates_file(monkeypatch, tmp_path: Path) -> None:
    example = tmp_path / "alerts.example.json"
    example.write_text('{"alerts": []}', encoding="utf-8")
    user_dir = tmp_path / "home" / ".market-helm"
    monkeypatch.setattr("src.alerts.alert_paths.bundled_example_path", lambda: example)
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    dest = init_user_alerts_config()
    assert dest == user_dir / "alerts.json"
    assert dest.exists()
