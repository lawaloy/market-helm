"""Tests for SMTP email alert delivery."""

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.email_notifier import EmailNotifier, _parse_recipients


def test_parse_recipients_accepts_comma_separated_string() -> None:
    assert _parse_recipients("a@example.com, b@example.com") == [
        "a@example.com",
        "b@example.com",
    ]


@patch.dict("os.environ", {}, clear=True)
def test_from_alert_returns_none_without_host() -> None:
    assert EmailNotifier.from_alert({"id": "a1", "notifications": ["email"]}) is None


@patch.dict(
    "os.environ",
    {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "bot@example.com",
        "SMTP_PASSWORD": "secret",
        "ALERT_EMAIL_TO": "you@example.com",
    },
    clear=True,
)
def test_from_alert_builds_from_environment() -> None:
    notifier = EmailNotifier.from_alert({"id": "a1", "notifications": ["email"]})
    assert notifier is not None
    assert notifier._host == "smtp.example.com"
    assert notifier._port == 587
    assert notifier._to_addrs == ["you@example.com"]


def test_from_alert_uses_email_to_field() -> None:
    notifier = EmailNotifier.from_alert(
        {
            "id": "a1",
            "notifications": ["email"],
            "smtp_host": "smtp.example.com",
            "smtp_user": "bot@example.com",
            "smtp_password": "secret",
            "email_to": ["ops@example.com", "backup@example.com"],
        }
    )
    assert notifier is not None
    assert notifier._to_addrs == ["ops@example.com", "backup@example.com"]


@patch("src.alerts.notifiers.email_notifier.smtplib.SMTP")
def test_send_uses_starttls_on_port_587(mock_smtp_cls: MagicMock) -> None:
    smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = smtp
    notifier = EmailNotifier(
        host="smtp.example.com",
        port=587,
        username="bot@example.com",
        password="secret",
        to_addrs=["you@example.com"],
    )
    event = {
        "alert_id": "x",
        "alert_name": "Test Alert",
        "symbols": ["AAPL"],
        "condition_type": "price_threshold",
        "timestamp": "2026-05-21T12:00:00",
    }
    notifier.send(event)
    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=15.0)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("bot@example.com", "secret")
    smtp.send_message.assert_called_once()


@patch("src.alerts.notifiers.email_notifier.smtplib.SMTP_SSL")
def test_send_uses_ssl_on_port_465(mock_smtp_cls: MagicMock) -> None:
    smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = smtp
    notifier = EmailNotifier(
        host="smtp.example.com",
        port=465,
        username="bot@example.com",
        password="secret",
        to_addrs=["you@example.com"],
        use_ssl=True,
        use_tls=False,
    )
    notifier.send({"alert_id": "x", "alert_name": "Test", "symbols": ["AAPL"]})
    mock_smtp_cls.assert_called_once_with("smtp.example.com", 465, timeout=15.0)
    smtp.starttls.assert_not_called()
    smtp.login.assert_called_once()
