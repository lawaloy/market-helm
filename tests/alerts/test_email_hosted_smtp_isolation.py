"""Hosted tenants must not override platform SMTP transport or From address."""

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.email_delivery import (
    _allow_alert_smtp_overrides,
    _platform_from_address,
    build_smtp_backend,
)
from src.alerts.notifiers.email_notifier import EmailNotifier


def test_allow_overrides_default_true_in_file_mode(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    assert _allow_alert_smtp_overrides({"id": "a1", "smtp_host": "evil.example"}) is True


def test_allow_overrides_default_false_when_database_enabled(monkeypatch) -> None:
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-smtp-iso.db"
    )
    assert _allow_alert_smtp_overrides({"id": "a1", "smtp_host": "evil.example"}) is False
    assert (
        _allow_alert_smtp_overrides(
            {"id": "a1", "smtp_host": "evil.example", "_allow_alert_smtp": True}
        )
        is True
    )


def test_platform_from_ignores_alert_email_from_in_hosted_mode(monkeypatch) -> None:
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-smtp-iso.db"
    )
    monkeypatch.setenv("ALERT_EMAIL_FROM", "platform@markethelm.example")

    assert (
        _platform_from_address(
            {"id": "a1", "email_from": "spoof@attacker.example"}
        )
        == "platform@markethelm.example"
    )


def test_platform_from_honors_alert_email_from_in_file_mode(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.delenv("ALERT_EMAIL_FROM", raising=False)

    assert (
        _platform_from_address({"id": "a1", "email_from": "ops@example.com"})
        == "ops@example.com"
    )


def test_build_smtp_backend_ignores_tenant_host_in_hosted_mode(monkeypatch) -> None:
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-smtp-iso.db"
    )
    monkeypatch.setenv("SMTP_HOST", "smtp.platform.example")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "platform-user")
    monkeypatch.setenv("SMTP_PASSWORD", "platform-pass")

    backend = build_smtp_backend(
        {
            "id": "a1",
            "smtp_host": "169.254.169.254",
            "smtp_port": 25,
            "smtp_user": "attacker",
            "smtp_password": "stolen",
        }
    )
    assert backend is not None
    assert backend._host == "smtp.platform.example"
    assert backend._port == 587
    assert backend._username == "platform-user"
    assert backend._password == "platform-pass"


def test_build_smtp_backend_uses_alert_overrides_in_file_mode(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    backend = build_smtp_backend(
        {
            "id": "a1",
            "smtp_host": "smtp.selfhost.example",
            "smtp_port": 465,
            "smtp_user": "self",
            "smtp_password": "secret",
        }
    )
    assert backend is not None
    assert backend._host == "smtp.selfhost.example"
    assert backend._port == 465
    assert backend._username == "self"


@patch("src.alerts.notifiers.email_delivery.SmtpEmailBackend.send", return_value=True)
def test_from_alert_uses_platform_smtp_not_tenant_host(
    mock_send: MagicMock, monkeypatch
) -> None:
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm-smtp-iso.db"
    )
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.platform.example")
    monkeypatch.setenv("SMTP_USER", "platform-user")
    monkeypatch.setenv("SMTP_PASSWORD", "platform-pass")
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@markethelm.example")

    notifier = EmailNotifier.from_alert(
        {
            "id": "a1",
            "notifications": ["email"],
            "email_to": "tenant@example.com",
            "email_from": "spoof@attacker.example",
            "smtp_host": "127.0.0.1",
            "smtp_user": "root",
            "smtp_password": "toor",
        }
    )
    assert notifier is not None
    assert notifier._from_addr == "alerts@markethelm.example"
    assert notifier._backend._host == "smtp.platform.example"
    mock_send.assert_not_called()
