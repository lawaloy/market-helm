"""CR/LF in .env values must not inject extra assignments."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.alerts.alert_paths import update_user_env_vars


def test_update_user_env_vars_rejects_newline_in_value(
    tmp_path: Path, monkeypatch
) -> None:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text("SHARED_KEEP=1\n", encoding="utf-8")
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    with pytest.raises(ValueError, match="CR/LF"):
        update_user_env_vars(
            {
                "DISCORD_WEBHOOK_URL": (
                    "https://discord.com/api/webhooks/x/y\nALERT_EMAIL_TO=evil@example.com"
                )
            }
        )

    assert env_file.read_text(encoding="utf-8") == "SHARED_KEEP=1\n"


def test_update_user_env_vars_rejects_crlf_in_key(
    tmp_path: Path, monkeypatch
) -> None:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text("SHARED_KEEP=1\n", encoding="utf-8")
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    with pytest.raises(ValueError, match="CR/LF"):
        update_user_env_vars({"BAD\nKEY": "value"})

    assert env_file.read_text(encoding="utf-8") == "SHARED_KEEP=1\n"


def test_update_user_env_vars_accepts_safe_webhook(
    tmp_path: Path, monkeypatch
) -> None:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    update_user_env_vars(
        {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/secret/token"}
    )

    assert (
        env_file.read_text(encoding="utf-8")
        == "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/secret/token\n"
    )
