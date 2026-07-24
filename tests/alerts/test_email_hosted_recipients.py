"""Hosted-mode email recipient isolation (process-wide ALERT_EMAIL_TO)."""

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.email_delivery import _resolve_recipients
from src.alerts.notifiers.email_notifier import EmailNotifier


def test_resolve_recipients_falls_back_to_env_in_file_mode(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("ALERT_EMAIL_TO", "shared@example.com")

    assert _resolve_recipients({"id": "a1"}) == ["shared@example.com"]


def test_resolve_recipients_ignores_env_when_database_enabled(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-email-iso.db")
    monkeypatch.setenv("ALERT_EMAIL_TO", "global-shared@example.com")

    assert _resolve_recipients({"id": "a1", "notifications": ["email"]}) == []


def test_resolve_recipients_uses_per_alert_email_in_database_mode(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-email-iso.db")
    monkeypatch.setenv("ALERT_EMAIL_TO", "global-shared@example.com")

    assert _resolve_recipients(
        {"id": "a1", "email_to": "tenant@example.com", "notifications": ["email"]}
    ) == ["tenant@example.com"]


def test_resolve_recipients_allows_explicit_env_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-email-iso.db")
    monkeypatch.setenv("ALERT_EMAIL_TO", "ops@example.com")

    assert _resolve_recipients({"id": "a1", "_allow_env_email": True}) == ["ops@example.com"]


@patch("src.alerts.notifiers.email_delivery.requests.post")
def test_from_alert_does_not_deliver_to_global_mailbox_in_hosted_mode(
    mock_post: MagicMock, monkeypatch
) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-email-iso.db")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setenv("SENDGRID_API_KEY", "sg-test-key")
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@markethelm.example")
    monkeypatch.setenv("ALERT_EMAIL_TO", "global-shared@example.com")

    assert EmailNotifier.from_alert({"id": "a1", "notifications": ["email"]}) is None
    mock_post.assert_not_called()
