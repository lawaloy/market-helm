"""Alert names / recipients must not inject CR/LF into email headers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.email_delivery import (
    format_alert_email,
    parse_recipients,
)
from src.alerts.notifiers.email_notifier import EmailNotifier


def test_format_alert_email_strips_crlf_from_alert_name() -> None:
    subject, body = format_alert_email(
        {
            "alert_id": "a1",
            "alert_name": "Price watch\r\nBcc: evil@example.com",
            "symbols": ["AAPL"],
            "condition_type": "price_threshold",
            "timestamp": "2026-06-09T12:00:00+00:00",
        }
    )
    assert "\r" not in subject
    assert "\n" not in subject
    assert "Bcc:" in subject  # neutralized into the single subject line
    assert subject.startswith("MarketHelm alert:")
    assert "\r" not in body.split("\n", 1)[0]


def test_parse_recipients_drops_crlf_and_malformed_addresses() -> None:
    assert parse_recipients("ok@example.com, evil\r\nBcc:x@example.com") == [
        "ok@example.com"
    ]
    assert parse_recipients(["ok@example.com", "nope\nevil@example.com"]) == [
        "ok@example.com"
    ]
    assert parse_recipients("not-an-email, also bad") == []
    assert parse_recipients("a@example.com") == ["a@example.com"]


@patch("src.alerts.notifiers.email_delivery.requests.post")
@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "sendgrid",
        "SENDGRID_API_KEY": "sg-test-key",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_sendgrid_subject_has_no_crlf_from_poisoned_alert_name(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(status_code=202, text="")
    notifier = EmailNotifier.from_alert({"id": "a1", "notifications": ["email"]})
    assert notifier is not None
    assert notifier.send(
        {
            "alert_id": "a1",
            "alert_name": "Watch\r\nBcc: attacker@example.com",
            "symbols": ["AAPL"],
            "condition_type": "price_threshold",
            "timestamp": "2026-06-09T12:00:00",
        }
    )
    subject = mock_post.call_args.kwargs["json"]["subject"]
    assert "\r" not in subject
    assert "\n" not in subject
