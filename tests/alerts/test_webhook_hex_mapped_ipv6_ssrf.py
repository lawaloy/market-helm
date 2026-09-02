"""Webhook SSRF must reject hex and expanded IPv4-mapped IPv6, not only dotted form.

``is_safe_webhook_url`` evaluates mapped addresses via the embedded IPv4
``is_global``. CPython still reports ``::ffff:6440:1`` (100.64.0.1) as
global. A check that only looks for dotted ``[::ffff:a.b.c.d]`` would miss
hex-mapped CGNAT and fully expanded ``0:0:0:0:0:ffff:…`` literals.
Locks: those encodings are rejected at ``from_alert``; hex-mapped public
IPv4 still allowed.
"""

from __future__ import annotations

import pytest

from src.alerts.notifiers.webhook_notifier import WebhookNotifier, is_safe_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        # 100.64.0.1 as IPv6 hex (CPython is_global=True without ipv4_mapped).
        "https://[::ffff:6440:1]/hook",
        # Same mapped CGNAT, fully expanded — not the compressed ::ffff: prefix.
        "https://[0:0:0:0:0:ffff:100.64.0.1]/hook",
        "https://[0:0:0:0:0:ffff:6440:1]/hook",
        # 127.0.0.1 as IPv6 hex — string checks for 127.0.0.1 miss this.
        "https://[::ffff:7f00:1]/hook",
    ],
)
def test_is_safe_webhook_url_rejects_hex_and_expanded_mapped(url: str) -> None:
    assert is_safe_webhook_url(url) is False


def test_is_safe_webhook_url_still_allows_hex_mapped_public_ipv4() -> None:
    """Hex-mapped public addresses must stay valid so the lock is not 'reject all hex IPv6'."""
    assert is_safe_webhook_url("https://[::ffff:808:808]/hook") is True  # 8.8.8.8


def test_from_alert_rejects_hex_mapped_cgnat() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://[::ffff:6440:1]/hooks/secret",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_rejects_expanded_mapped_cgnat() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://[0:0:0:0:0:ffff:100.64.0.1]/hooks/secret",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_still_accepts_hex_mapped_public_ipv4() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://[::ffff:808:808]/hooks/T/B/X",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._url == "https://[::ffff:808:808]/hooks/T/B/X"
