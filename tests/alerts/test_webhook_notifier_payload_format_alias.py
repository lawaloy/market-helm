"""from_alert must honor legacy payload_format when webhook_format is absent.

Older alerts.json / CLI-edited configs store Slack/Discord as ``payload_format``.
``from_alert`` prefers ``webhook_format``, then ``payload_format``, then env.
Constructor tests pass ``payload_format=`` directly; env tests set
``ALERT_WEBHOOK_FORMAT``. Neither hits the alert-dict alias. A regression that
dropped that branch would POST raw JSON to Slack/Discord webhooks.
"""

from unittest.mock import patch

from src.alerts.notifiers.webhook_notifier import WebhookNotifier

_EVENT = {
    "alert_id": "a1",
    "alert_name": "Drop",
    "symbols": ["AAPL"],
    "condition_type": "price_threshold",
    "timestamp": "2026-05-21T12:00:00",
}


@patch.dict("os.environ", {}, clear=True)
def test_from_alert_legacy_payload_format_is_slack_after_strip() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://example.com/hook",
            "payload_format": " Slack ",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._payload_format == "slack"
    payload = notifier.build_payload(_EVENT)
    assert "text" in payload
    assert "blocks" in payload
    assert "Drop" in payload["text"]


@patch.dict("os.environ", {}, clear=True)
def test_from_alert_webhook_format_wins_over_legacy_payload_format() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://example.com/hook",
            "webhook_format": "discord",
            "payload_format": "slack",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._payload_format == "discord"
    payload = notifier.build_payload(_EVENT)
    assert "content" in payload
    assert "blocks" not in payload


@patch.dict("os.environ", {"ALERT_WEBHOOK_FORMAT": "json"}, clear=True)
def test_from_alert_legacy_payload_format_wins_over_env() -> None:
    notifier = WebhookNotifier.from_alert(
        {
            "id": "a1",
            "webhook_url": "https://example.com/hook",
            "payload_format": "discord",
            "notifications": ["webhook"],
        }
    )
    assert notifier is not None
    assert notifier._payload_format == "discord"
    payload = notifier.build_payload(_EVENT)
    assert payload["content"].startswith("**MarketHelm alert:** Drop")
    assert "blocks" not in payload
