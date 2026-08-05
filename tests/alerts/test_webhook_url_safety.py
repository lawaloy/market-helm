"""Webhook URL safety: reject non-HTTPS and obvious SSRF targets at from_alert."""

from __future__ import annotations

import pytest

from src.alerts.notifiers.webhook_notifier import WebhookNotifier, is_safe_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.slack.com/services/T/B/X",
        "https://discord.com/api/webhooks/1/token",
        "https://example.com/hook",
        "https://alerts.example.org/v1/notify",
        "  https://hooks.example.com/path  ",
    ],
)
def test_is_safe_webhook_url_allows_public_https(url: str) -> None:
    assert is_safe_webhook_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "http://hooks.example.com/hook",
        "ftp://hooks.example.com/hook",
        "hooks.example.com/hook",
        "//hooks.example.com/hook",
        "https://",
        "https:///path",
        "https://user:pass@hooks.example.com/hook",
        "https://user@hooks.example.com/hook",
        "https://localhost/hook",
        "https://localhost:8443/hook",
        "https://foo.localhost/hook",
        "https://127.0.0.1/hook",
        "https://127.0.0.1:8443/hook",
        "https://[::1]/hook",
        "https://0.0.0.0/hook",
        "https://10.0.0.5/hook",
        "https://172.16.0.1/hook",
        "https://172.31.255.255/hook",
        "https://192.168.1.10/hook",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://metadata/computeMetadata/v1/",
        "https://[fc00::1]/hook",
        "https://[fe80::1]/hook",
    ],
)
def test_is_safe_webhook_url_rejects_unsafe(url: str) -> None:
    assert is_safe_webhook_url(url) is False


def test_from_alert_rejects_http_url() -> None:
    assert (
        WebhookNotifier.from_alert(
            {"id": "a1", "webhook_url": "http://hooks.example.com/hook"}
        )
        is None
    )


def test_from_alert_rejects_loopback_https() -> None:
    assert (
        WebhookNotifier.from_alert(
            {"id": "a1", "webhook_url": "https://127.0.0.1/internal"}
        )
        is None
    )


def test_from_alert_rejects_private_https() -> None:
    assert (
        WebhookNotifier.from_alert(
            {"id": "a1", "webhook_url": "https://10.1.2.3/hooks/secret"}
        )
        is None
    )


def test_from_alert_rejects_metadata_host() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://169.254.169.254/latest/meta-data/",
            }
        )
        is None
    )


def test_from_alert_rejects_unsafe_env_fallback(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://127.0.0.1:8080/hook")
    assert WebhookNotifier.from_alert({"id": "a1", "notifications": ["webhook"]}) is None


def test_from_alert_still_accepts_public_https() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://hooks.example.com/services/T/B/X",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._url == "https://hooks.example.com/services/T/B/X"
