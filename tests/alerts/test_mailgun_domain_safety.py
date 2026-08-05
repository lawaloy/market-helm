"""MAILGUN_DOMAIN must be a hostname segment — never reshape the messages URL."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.alerts.notifiers.email_delivery import (
    MailgunEmailBackend,
    build_mailgun_backend,
    normalize_mailgun_domain,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("mg.markethelm.example", "mg.markethelm.example"),
        (" MG.MarketHelm.Example ", "mg.markethelm.example"),
        ("sandbox123.mailgun.org", "sandbox123.mailgun.org"),
    ],
)
def test_normalize_mailgun_domain_allows_hostnames(raw: str, expected: str) -> None:
    assert normalize_mailgun_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "mg.example/evil",
        "mg.example\\evil",
        "user@mg.example",
        "mg.example messages",
        "mg.example\nother",
        "mg.example\rother",
        "mg.example\0x",
        ".mg.example",
        "mg.example.",
        "mg..example",
        "-mg.example",
        "mg-.example",
        "https://mg.example",
    ],
)
def test_normalize_mailgun_domain_rejects_path_and_injection_shapes(raw: str) -> None:
    assert normalize_mailgun_domain(raw) is None


@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "mailgun",
        "MAILGUN_API_KEY": "mg-test-key",
        "MAILGUN_DOMAIN": "mg.markethelm.example",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_build_mailgun_backend_accepts_safe_domain() -> None:
    backend = build_mailgun_backend()
    assert isinstance(backend, MailgunEmailBackend)
    assert backend._domain == "mg.markethelm.example"


@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "mailgun",
        "MAILGUN_API_KEY": "mg-test-key",
        "MAILGUN_DOMAIN": "mg.example/../../evil",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_build_mailgun_backend_rejects_path_injection_domain() -> None:
    assert build_mailgun_backend() is None


@patch.dict(
    "os.environ",
    {
        "ALERT_EMAIL_PROVIDER": "mailgun",
        "MAILGUN_API_KEY": "mg-test-key",
        "MAILGUN_DOMAIN": "user@mg.example",
        "ALERT_EMAIL_FROM": "alerts@markethelm.example",
        "ALERT_EMAIL_TO": "user@example.com",
    },
    clear=True,
)
def test_build_mailgun_backend_rejects_at_sign_domain() -> None:
    assert build_mailgun_backend() is None
