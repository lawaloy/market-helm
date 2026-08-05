"""Hosted-mode webhook URL/format isolation (process-wide env must not leak)."""

from src.alerts.notifiers.webhook_notifier import WebhookNotifier


def test_from_alert_ignores_env_url_and_format_when_database_enabled(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-webhook-iso.db")
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example/global")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/global/token")
    monkeypatch.setenv("ALERT_WEBHOOK_FORMAT", "slack")

    assert WebhookNotifier.from_alert({"id": "a1", "notifications": ["webhook"]}) is None


def test_from_alert_uses_alert_url_but_ignores_env_format_when_hosted(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-webhook-iso.db")
    monkeypatch.setenv("ALERT_WEBHOOK_FORMAT", "slack")
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://tenant.example/hook",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._url == "https://tenant.example/hook"
    # Hosted mode must not inherit process-wide format defaults.
    assert notifier._payload_format == "json"


def test_from_alert_honors_per_alert_format_in_hosted_mode(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-webhook-iso.db")
    monkeypatch.setenv("ALERT_WEBHOOK_FORMAT", "slack")

    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://tenant.example/hook",
            "webhook_format": "discord",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._payload_format == "discord"


def test_from_alert_explicit_env_opt_out_ignores_url(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example/global")

    assert (
        WebhookNotifier.from_alert(
            {"id": "a1", "notifications": ["webhook"], "_allow_env_webhook": False}
        )
        is None
    )


def test_from_alert_explicit_env_opt_in_uses_url_when_hosted(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-webhook-iso.db")
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example/ops")
    monkeypatch.setenv("ALERT_WEBHOOK_FORMAT", "slack")

    notifier = WebhookNotifier.from_alert(
        {"id": "a1", "notifications": ["webhook"], "_allow_env_webhook": True}
    )
    assert notifier is not None
    assert notifier._url == "https://hooks.example/ops"
    assert notifier._payload_format == "slack"
