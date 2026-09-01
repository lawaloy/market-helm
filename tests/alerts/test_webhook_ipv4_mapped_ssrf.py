"""Webhook SSRF must reject IPv4-mapped and CGNAT literals, not only RFC1918.

``is_safe_webhook_url`` already uses ``ipaddress.ip_address(...).is_global``.
A regression that only blocked dotted-quad loopback / 10/8 would still POST
alert payloads (and any tenant webhook secret) to ``[::ffff:127.0.0.1]`` or
carrier-grade NAT ``100.64.0.0/10``. Locks: mapped loopback/private/metadata
and CGNAT are rejected at ``from_alert``; mapped public IPv4 still allowed.
"""

from __future__ import annotations

import pytest

from src.alerts.notifiers.webhook_notifier import WebhookNotifier, is_safe_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        "https://[::ffff:127.0.0.1]/hook",
        "https://[::ffff:10.1.2.3]/hooks/secret",
        "https://[::ffff:169.254.169.254]/latest/meta-data/",
        "https://100.64.0.1/hook",
        "https://100.127.255.254/hook",
    ],
)
def test_is_safe_webhook_url_rejects_ipv4_mapped_and_cgnat(url: str) -> None:
    assert is_safe_webhook_url(url) is False


def test_is_safe_webhook_url_still_allows_public_ipv4_mapped() -> None:
    """Mapped public addresses must stay valid so the lock is not 'reject all IPv6'."""
    assert is_safe_webhook_url("https://[::ffff:8.8.8.8]/hook") is True
    assert is_safe_webhook_url("https://8.8.8.8/hook") is True


def test_from_alert_rejects_ipv4_mapped_loopback() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://[::ffff:127.0.0.1]/internal",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_rejects_cgnat_https() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://100.64.0.1/hooks/secret",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_still_accepts_public_ipv4_mapped() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://[::ffff:8.8.8.8]/hooks/T/B/X",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._url == "https://[::ffff:8.8.8.8]/hooks/T/B/X"
