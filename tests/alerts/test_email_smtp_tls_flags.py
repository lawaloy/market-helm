"""build_smtp_backend must infer STARTTLS/SSL from port and SMTP_USE_* env.

Send tests construct ``SmtpEmailBackend`` directly (constructor defaults
``use_tls=True``). File-mode / hosted SMTP still goes through
``build_smtp_backend``, which is the only path that reads ``SMTP_USE_SSL`` /
``SMTP_USE_TLS`` and the 465/587 port defaults. A regression that dropped
``default=port == 587`` would send alert mail in the clear on submission port.
"""

from unittest.mock import patch

from src.alerts.notifiers.email_delivery import build_smtp_backend

_SMTP = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USER": "user@example.com",
    "SMTP_PASSWORD": "secret",
}


@patch.dict("os.environ", _SMTP, clear=True)
def test_build_smtp_backend_defaults_to_starttls_on_port_587() -> None:
    """Unset SMTP_PORT is 587; unset SMTP_USE_TLS must still STARTTLS."""
    backend = build_smtp_backend({})
    assert backend is not None
    assert backend._port == 587
    assert backend._use_ssl is False
    assert backend._use_tls is True


@patch.dict("os.environ", {**_SMTP, "SMTP_PORT": "465"}, clear=True)
def test_build_smtp_backend_infers_ssl_from_port_465_without_env() -> None:
    """Port 465 is implicit SMTPS even when SMTP_USE_SSL is unset."""
    backend = build_smtp_backend({})
    assert backend is not None
    assert backend._port == 465
    assert backend._use_ssl is True
    assert backend._use_tls is False


@patch.dict(
    "os.environ",
    {**_SMTP, "SMTP_PORT": "587", "SMTP_USE_TLS": "false"},
    clear=True,
)
def test_build_smtp_backend_honors_tls_off_on_submission_port() -> None:
    """SMTP_USE_TLS=false must not keep the port-587 STARTTLS default."""
    backend = build_smtp_backend({})
    assert backend is not None
    assert backend._use_ssl is False
    assert backend._use_tls is False


@patch.dict(
    "os.environ",
    {**_SMTP, "SMTP_PORT": "587", "SMTP_USE_SSL": "1"},
    clear=True,
)
def test_build_smtp_backend_ssl_env_suppresses_starttls_on_587() -> None:
    """Implicit SSL (env alias ``1``) must win over the 587 STARTTLS default."""
    backend = build_smtp_backend({})
    assert backend is not None
    assert backend._use_ssl is True
    assert backend._use_tls is False


@patch.dict(
    "os.environ",
    {**_SMTP, "SMTP_PORT": "25", "SMTP_USE_TLS": " yes "},
    clear=True,
)
def test_build_smtp_backend_tls_yes_enables_starttls_on_port_25() -> None:
    """Padded SMTP_USE_TLS=yes must STARTTLS on a non-587 port (not plaintext)."""
    backend = build_smtp_backend({})
    assert backend is not None
    assert backend._port == 25
    assert backend._use_ssl is False
    assert backend._use_tls is True
