"""From addresses must not carry CR/LF into SMTP / provider payloads."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.email_delivery import _platform_from_address, _safe_from_address
from src.alerts.notifiers.email_notifier import EmailNotifier


def test_safe_from_address_rejects_crlf() -> None:
    assert _safe_from_address("alerts@example.com") == "alerts@example.com"
    assert (
        _safe_from_address("MarketHelm Alerts <alerts@example.com>")
        == "MarketHelm Alerts <alerts@example.com>"
    )
    assert _safe_from_address("alerts@example.com\r\nBcc: evil@example.com") is None
    assert _safe_from_address("alerts@example.com\nBcc: evil@example.com") is None
    assert _safe_from_address("   ") is None


def test_platform_from_skips_poisoned_alert_email_from(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("ALERT_EMAIL_FROM", "platform@markethelm.example")
    assert (
        _platform_from_address(
            {
                "id": "a1",
                "email_from": "spoof@attacker.example\r\nBcc: victim@example.com",
            }
        )
        == "platform@markethelm.example"
    )


def test_platform_from_rejects_poisoned_env_from(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "ALERT_EMAIL_FROM", "alerts@example.com\nBcc: evil@example.com"
    )
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "sendgrid")
    monkeypatch.delenv("SMTP_USER", raising=False)
    assert _platform_from_address({"id": "a1"}) is None


@patch("src.alerts.notifiers.email_delivery.requests.post")
@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "sendgrid",
        "SENDGRID_API_KEY": "sg-test-key",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example\r\nBcc: evil@example.com",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_sendgrid_notifier_refuses_poisoned_from(mock_post: MagicMock) -> None:
    notifier = EmailNotifier.from_alert({"id": "a1", "notifications": ["email"]})
    assert notifier is None
    mock_post.assert_not_called()
