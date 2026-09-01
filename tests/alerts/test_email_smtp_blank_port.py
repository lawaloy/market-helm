"""build_smtp_backend must treat blank alert smtp_port as unset.

File-mode / CLI configs persist ``smtp_port`` as ``""`` or ``"   "``. A truthy
``port_raw or env`` keeps whitespace, ``int("   ")`` raises, and the backend
returns None — alert email is dropped. The strip-empty check must fall back to
``SMTP_PORT`` / 587 and still infer STARTTLS vs implicit SSL from that port.
"""

from unittest.mock import patch

from src.alerts.notifiers.email_delivery import build_smtp_backend
from src.alerts.notifiers.email_notifier import EmailNotifier

_SMTP = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USER": "user@example.com",
    "SMTP_PASSWORD": "secret",
}

_ALERT = {
    "id": "a1",
    "notifications": ["email"],
    "email_to": "ops@example.com",
    "smtp_host": "smtp.example.com",
    "smtp_user": "user@example.com",
    "smtp_password": "secret",
}


@patch.dict("os.environ", _SMTP, clear=True)
def test_empty_alert_smtp_port_falls_back_to_587_starttls() -> None:
    """Empty smtp_port is unset, not invalid — default submission port + STARTTLS."""
    backend = build_smtp_backend({**_ALERT, "smtp_port": ""})
    assert backend is not None
    assert backend._port == 587
    assert backend._use_ssl is False
    assert backend._use_tls is True

    notifier = EmailNotifier.from_alert({**_ALERT, "smtp_port": ""})
    assert notifier is not None
    assert notifier._backend._port == 587
    assert notifier._backend._use_ssl is False
    assert notifier._backend._use_tls is True


@patch.dict("os.environ", {**_SMTP, "SMTP_PORT": "465"}, clear=True)
def test_padded_blank_alert_smtp_port_falls_back_to_env_465_ssl() -> None:
    """Whitespace smtp_port must not stay truthy; env 465 must still imply SMTPS."""
    backend = build_smtp_backend({**_ALERT, "smtp_port": "   "})
    assert backend is not None
    assert backend._port == 465
    assert backend._use_ssl is True
    assert backend._use_tls is False

    notifier = EmailNotifier.from_alert({**_ALERT, "smtp_port": "   "})
    assert notifier is not None
    assert notifier._backend._port == 465
    assert notifier._backend._use_ssl is True
    assert notifier._backend._use_tls is False
