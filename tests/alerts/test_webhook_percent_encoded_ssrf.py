"""Webhook SSRF must reject percent-encoded loopback / private hosts.

``urlparse().hostname`` leaves ``%31%32%37.%30.%30.%31`` encoded, so the
literal-IP and blocked-host checks previously treated it as a DNS name.
``requests`` prepares that URL as ``127.0.0.1`` and connects to loopback.
Locks: encoded loopback/localhost/private/metadata/hex-IPv4 are rejected at
``from_alert``; percent-encoded public hostnames still allowed.
"""

from __future__ import annotations

import pytest
from requests.models import PreparedRequest

from src.alerts.notifiers.webhook_notifier import WebhookNotifier, is_safe_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        "https://%31%32%37.%30.%30.%31/hook",
        "https://%31%32%37.%30.%30.%31:8443/hook",
        "https://127%2e0%2e0%2e1/hook",
        "https://%31%32%37%2e%30%2e%30%2e%31/hook",
        "https://127.0.0.%31/hook",
        "https://%6c%6f%63%61%6c%68%6f%73%74/hook",
        "https://%4c%6f%63%61%6c%68%6f%73%74/hook",
        "https://%31%36%39.%32%35%34.%31%36%39.%32%35%34/latest/meta-data/",
        "https://169%2e254%2e169%2e254/latest/meta-data/",
        "https://%31%30.0.0.1/hook",
        "https://192%2e168%2e1%2e1/hook",
        # Hex loopback with a percent-encoded leading 0; requests prepares 0x7f000001.
        "https://%30x7f000001/hook",
        # Double-encoded loopback still unwraps to 127.0.0.1.
        "https://%2531%2532%2537.%2530.%2530.%2531/hook",
        "https://127.0.0.1%2e/hook",
    ],
)
def test_is_safe_webhook_url_rejects_percent_encoded_private_hosts(url: str) -> None:
    assert is_safe_webhook_url(url) is False


def test_is_safe_webhook_url_still_allows_percent_encoded_public_host() -> None:
    """Encoding a public DNS name must stay valid (not 'reject all % in hosts')."""
    assert is_safe_webhook_url("https://%65%78%61%6d%70%6c%65.%63%6f%6d/hook") is True
    assert is_safe_webhook_url("https://hooks.%65xample.com/hook") is True


def test_requests_prepares_percent_encoded_loopback_as_127() -> None:
    """Lock the trigger: requests decodes the host before connecting."""
    req = PreparedRequest()
    req.prepare(method="POST", url="https://%31%32%37.%30.%30.%31:8443/hook")
    assert req.url == "https://127.0.0.1:8443/hook"
    assert is_safe_webhook_url("https://%31%32%37.%30.%30.%31:8443/hook") is False


def test_from_alert_rejects_percent_encoded_loopback() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://%31%32%37.%30.%30.%31:8443/internal",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_rejects_percent_encoded_localhost() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://%6c%6f%63%61%6c%68%6f%73%74/hook",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_rejects_percent_encoded_metadata() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://%31%36%39.%32%35%34.%31%36%39.%32%35%34/latest/meta-data/",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_still_accepts_percent_encoded_public_host() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://%65%78%61%6d%70%6c%65.%63%6f%6d/hook",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._url == "https://%65%78%61%6d%70%6c%65.%63%6f%6d/hook"
