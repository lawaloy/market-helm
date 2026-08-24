"""Account emails must only embed a safe public dashboard origin."""

from unittest.mock import MagicMock

import pytest

from dashboard.backend.account_email import send_account_email


@pytest.fixture
def configured_backend(monkeypatch):
    backend = MagicMock()
    backend.send.return_value = True
    monkeypatch.setattr(
        "dashboard.backend.account_email.build_email_backend",
        lambda _cfg: backend,
    )
    monkeypatch.setattr(
        "dashboard.backend.account_email._platform_from_address",
        lambda: "alerts@markethelm.example",
    )
    return backend


@pytest.mark.parametrize(
    "public_url",
    [
        "",
        "http://evil.example",
        "https://user:pass@staging.example.com",
        "https://staging.example.com/reset",
        "https://staging.example.com?next=https://evil.example",
        "https://staging.example.com#token=stolen",
        "javascript:alert(1)",
        "ftp://staging.example.com",
    ],
)
def test_unsafe_public_url_does_not_send(configured_backend, monkeypatch, public_url):
    monkeypatch.setenv("MARKET_HELM_PUBLIC_URL", public_url)
    sent = send_account_email(
        recipient="user@example.com",
        purpose="reset_password",
        token="reset-token",
    )
    assert sent is False
    configured_backend.send.assert_not_called()


def test_https_public_url_embeds_verify_link(configured_backend, monkeypatch):
    monkeypatch.setenv("MARKET_HELM_PUBLIC_URL", "https://staging.example.com")
    sent = send_account_email(
        recipient="user@example.com",
        purpose="verify_email",
        token="verify-token",
    )
    assert sent is True
    kwargs = configured_backend.send.call_args.kwargs
    assert kwargs["to_addrs"] == ["user@example.com"]
    assert kwargs["from_addr"] == "alerts@markethelm.example"
    assert "https://staging.example.com/verify-email?token=verify-token" in kwargs["body"]
    assert "Reset your MarketHelm password" not in kwargs["subject"]


def test_localhost_http_embeds_reset_link(configured_backend, monkeypatch):
    monkeypatch.setenv("MARKET_HELM_PUBLIC_URL", "http://127.0.0.1:3000")
    sent = send_account_email(
        recipient="user@example.com",
        purpose="reset_password",
        token="reset-token",
    )
    assert sent is True
    kwargs = configured_backend.send.call_args.kwargs
    assert "http://127.0.0.1:3000/reset-password?token=reset-token" in kwargs["body"]
    assert kwargs["subject"] == "Reset your MarketHelm password"


def test_missing_backend_does_not_send(monkeypatch):
    monkeypatch.setenv("MARKET_HELM_PUBLIC_URL", "https://staging.example.com")
    monkeypatch.setattr(
        "dashboard.backend.account_email.build_email_backend",
        lambda _cfg: None,
    )
    monkeypatch.setattr(
        "dashboard.backend.account_email._platform_from_address",
        lambda: "alerts@markethelm.example",
    )
    assert send_account_email(
        recipient="user@example.com",
        purpose="verify_email",
        token="verify-token",
    ) is False
