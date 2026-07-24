"""Tests for alert config path resolution."""

from pathlib import Path

from src.alerts.alert_paths import (
    apply_alert_defaults,
    update_user_env_vars,
    init_user_alerts_config,
    load_alerts_config,
    polish_alerts_config,
    resolve_alerts_config_path,
    save_alerts_config,
    dedupe_alerts_config,
    strip_webhook_secrets_from_config,
)


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


def test_save_and_load_alerts_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "alerts.json"
    monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_path))
    monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    payload = {"defaults": {"email_to": "a@example.com"}, "alerts": []}
    save_alerts_config(payload)
    path, loaded = load_alerts_config()
    assert path == config_path
    assert loaded == payload


def test_polish_alerts_config_strips_placeholders(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_EMAIL_TO", "real@example.org")
    config = {
        "alerts": [
            {
                "id": "a1",
                "email_to": "you@example.com",
                "webhook_url": "https://hooks.example.com/x",
                "notifications": ["email", "webhook"],
            }
        ]
    }
    polished = polish_alerts_config(config)
    assert polished["defaults"]["email_to"] == "real@example.org"
    assert "email_to" not in polished["alerts"][0]
    assert "webhook_url" not in polished["alerts"][0]


def test_dedupe_alerts_config_keeps_first_price_rule() -> None:
    config = {
        "alerts": [
            {
                "id": "aapl_drop",
                "condition": {"type": "price_threshold", "symbol": "AAPL", "operator": "less_than", "value": 150},
            },
            {
                "id": "aapl_drop_copy",
                "condition": {"type": "price_threshold", "symbol": "AAPL", "operator": "less_than", "value": 150},
            },
            {
                "id": "msft_high",
                "condition": {"type": "price_threshold", "symbol": "MSFT", "operator": "greater_than", "value": 400},
            },
        ]
    }
    deduped = dedupe_alerts_config(config)
    assert len(deduped["alerts"]) == 2
    assert deduped["alerts"][0]["id"] == "aapl_drop"


def test_strip_webhook_secrets_from_config() -> None:
    config = {
        "defaults": {"webhook_url": "https://discord.com/secret", "email_to": "a@example.com"},
        "alerts": [{"id": "x", "webhook_url": "https://discord.com/secret"}],
    }
    stripped = strip_webhook_secrets_from_config(config)
    assert "webhook_url" not in stripped["defaults"]
    assert "webhook_url" not in stripped["alerts"][0]
    assert stripped["defaults"]["email_to"] == "a@example.com"


def test_update_user_env_vars_replaces_webhook_values_without_dropping_other_settings(
    tmp_path: Path, monkeypatch
) -> None:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text(
        "\n".join(
            [
                "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/old/token",
                "ALERT_EMAIL_TO=alerts@example.com",
                "ALERT_WEBHOOK_FORMAT=slack",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    update_user_env_vars(
        {
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/new/token",
            "ALERT_WEBHOOK_FORMAT": "discord",
        }
    )

    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/new/token",
        "ALERT_EMAIL_TO=alerts@example.com",
        "ALERT_WEBHOOK_FORMAT=discord",
    ]


def test_update_user_env_vars_empty_value_deletes_key(
    tmp_path: Path, monkeypatch
) -> None:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text(
        "\n".join(
            [
                "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/secret/token",
                "ALERT_EMAIL_TO=alerts@example.com",
                "ALERT_WEBHOOK_FORMAT=discord",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    update_user_env_vars({"DISCORD_WEBHOOK_URL": ""})

    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "ALERT_EMAIL_TO=alerts@example.com",
        "ALERT_WEBHOOK_FORMAT=discord",
    ]
    assert "DISCORD_WEBHOOK_URL" not in env_file.read_text(encoding="utf-8")


def test_apply_alert_defaults_merges_email_and_webhook() -> None:
    alert = {"notifications": ["email", "webhook"]}
    defaults = {"email_to": "a@example.com", "webhook_url": "https://example.com/hook"}
    merged = apply_alert_defaults(alert, defaults)
    assert merged["email_to"] == "a@example.com"
    assert merged["webhook_url"] == "https://example.com/hook"
