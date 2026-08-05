"""MAILGUN_API_BASE must only target official Mailgun HTTPS API origins."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.alerts.notifiers.email_delivery import (
    MailgunEmailBackend,
    build_mailgun_backend,
    normalize_mailgun_api_base,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://api.mailgun.net", "https://api.mailgun.net"),
        ("https://api.mailgun.net/", "https://api.mailgun.net"),
        ("https://api.eu.mailgun.net", "https://api.eu.mailgun.net"),
        (" https://api.eu.mailgun.net/ ", "https://api.eu.mailgun.net"),
    ],
)
def test_normalize_mailgun_api_base_allows_official_origins(raw: str, expected: str) -> None:
    assert normalize_mailgun_api_base(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "http://api.mailgun.net",
        "https://api.mailgun.net/v3",
        "https://api.mailgun.net?x=1",
        "https://attacker.example",
        "https://127.0.0.1",
        "https://api.mailgun.net:8443",
        "https://user:pass@api.mailgun.net",
        "ftp://api.mailgun.net",
        "api.mailgun.net",
    ],
)
def test_normalize_mailgun_api_base_rejects_unsafe_values(raw: str) -> None:
    assert normalize_mailgun_api_base(raw) is None


@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "mailgun",
        "MAILGUN_API_KEY": "mg-test-key",
        "MAILGUN_DOMAIN": "mg.markethelm.example",
        "MAILGUN_API_BASE": "https://api.eu.mailgun.net/",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_build_mailgun_backend_accepts_eu_api_base() -> None:
    backend = build_mailgun_backend()
    assert isinstance(backend, MailgunEmailBackend)
    assert backend._api_base == "https://api.eu.mailgun.net"


@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "mailgun",
        "MAILGUN_API_KEY": "mg-test-key",
        "MAILGUN_DOMAIN": "mg.markethelm.example",
        "MAILGUN_API_BASE": "http://127.0.0.1:8080",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_build_mailgun_backend_rejects_non_https_api_base() -> None:
    assert build_mailgun_backend() is None


@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "mailgun",
        "MAILGUN_API_KEY": "mg-test-key",
        "MAILGUN_DOMAIN": "mg.markethelm.example",
        "MAILGUN_API_BASE": "https://evil.example/mailgun",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_build_mailgun_backend_rejects_unapproved_api_host() -> None:
    assert build_mailgun_backend() is None
