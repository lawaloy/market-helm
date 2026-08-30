"""Keys with '=' or NUL must not inject extra .env assignments."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.alerts.alert_paths import update_user_env_vars


def _prepare_env(tmp_path: Path, monkeypatch) -> Path:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text("SHARED_KEEP=1\n", encoding="utf-8")
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)
    return env_file


def test_update_user_env_vars_rejects_equals_in_key(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = _prepare_env(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="="):
        update_user_env_vars({"FAKE=ALERT_EMAIL_TO": "evil@example.com"})

    assert env_file.read_text(encoding="utf-8") == "SHARED_KEEP=1\n"


def test_update_user_env_vars_rejects_nul_in_key(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = _prepare_env(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="NUL"):
        update_user_env_vars({"BAD\0KEY": "value"})

    assert env_file.read_text(encoding="utf-8") == "SHARED_KEEP=1\n"


def test_update_user_env_vars_rejects_nul_in_value(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = _prepare_env(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="NUL"):
        update_user_env_vars({"DISCORD_WEBHOOK_URL": "https://example.test/x\0y"})

    assert env_file.read_text(encoding="utf-8") == "SHARED_KEEP=1\n"


def test_update_user_env_vars_allows_equals_in_value(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = _prepare_env(tmp_path, monkeypatch)

    update_user_env_vars(
        {"CUSTOM_WEBHOOK_URL": "https://hooks.example/path?token=secret"}
    )

    assert env_file.read_text(encoding="utf-8") == (
        "SHARED_KEEP=1\n"
        "CUSTOM_WEBHOOK_URL=https://hooks.example/path?token=secret\n"
    )
