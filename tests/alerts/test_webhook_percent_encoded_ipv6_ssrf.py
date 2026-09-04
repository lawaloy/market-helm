"""Webhook SSRF must reject percent-encoded IPv6 loopback / link-local hosts.

``urlparse().hostname`` leaves ``[::%31]`` encoded as ``::%31``, so the
literal-IP check previously treated it as a non-IP DNS name. ``requests``
prepares that URL as ``[::1]`` and connects to IPv6 loopback. #608 locked
percent-encoded IPv4 / localhost labels only. Locks: encoded IPv6 loopback,
unspecified, link-local, and ULA are rejected at ``from_alert``; native
public IPv6 still allowed.
"""

from __future__ import annotations

import pytest
from requests.models import PreparedRequest

from src.alerts.notifiers.webhook_notifier import WebhookNotifier, is_safe_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        "https://[::%31]/hook",
        "https://[::%31]:8443/hook",
        # Encoded unspecified (::0) — not global, still a bind-any target.
        "https://[::%30]/hook",
        "https://[fe80::%31]/hook",
        "https://[fc00::%31]/hook",
    ],
)
def test_is_safe_webhook_url_rejects_percent_encoded_ipv6_private_hosts(
    url: str,
) -> None:
    assert is_safe_webhook_url(url) is False


def test_is_safe_webhook_url_still_allows_native_public_ipv6() -> None:
    """A public IPv6 literal must stay valid (not 'reject all IPv6')."""
    assert is_safe_webhook_url("https://[2001:4860:4860::8888]/hook") is True
    assert is_safe_webhook_url("https://[2606:4700:4700::1111]/hook") is True


def test_requests_prepares_percent_encoded_ipv6_loopback_as_unspecified_one() -> None:
    """Lock the trigger: requests decodes ``::%31`` to ``::1`` before connecting."""
    req = PreparedRequest()
    req.prepare(method="POST", url="https://[::%31]:8443/hook")
    assert req.url == "https://[::1]:8443/hook"
    assert is_safe_webhook_url("https://[::%31]:8443/hook") is False


def test_from_alert_rejects_percent_encoded_ipv6_loopback() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://[::%31]:8443/internal",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_rejects_percent_encoded_ipv6_link_local() -> None:
    assert (
        WebhookNotifier.from_alert(
            {
                "id": "a1",
                "webhook_url": "https://[fe80::%31]/hook",
                "notifications": ["webhook"],
            }
        )
        is None
    )


def test_from_alert_still_accepts_native_public_ipv6() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://[2001:4860:4860::8888]/hooks/T/B/X",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._url == "https://[2001:4860:4860::8888]/hooks/T/B/X"
