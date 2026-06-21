"""Tests for webhook alert delivery."""

from unittest.mock import MagicMock, patch

import requests

from src.alerts.notifiers.webhook_notifier import WebhookNotifier


def test_from_alert_returns_none_without_url() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert WebhookNotifier.from_alert({"id": "a1", "notifications": ["webhook"]}) is None


def test_from_alert_uses_webhook_url_field() -> None:
    n = WebhookNotifier.from_alert(
        {"id": "a1", "webhook_url": "https://example.com/hook", "notifications": ["webhook"]}
    )
    assert n is not None
    assert n._url == "https://example.com/hook"


@patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://env.example/hook"}, clear=False)
def test_from_alert_falls_back_to_env() -> None:
    n = WebhookNotifier.from_alert({"id": "a1", "notifications": ["webhook"]})
    assert n is not None
    assert n._url == "https://env.example/hook"


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_posts_json(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 200
    notifier = WebhookNotifier("https://example.com/hook")
    event = {"alert_id": "x", "symbols": ["AAPL"]}
    assert notifier.send(event) is True
    mock_post.assert_called_once()
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == event
    assert kwargs["timeout"] == 10.0


def test_build_payload_slack_format() -> None:
    notifier = WebhookNotifier("https://example.com/hook", payload_format="slack")
    payload = notifier.build_payload(
        {
            "alert_id": "x",
            "alert_name": "Drop",
            "symbols": ["AAPL"],
            "condition_type": "price_threshold",
            "timestamp": "2026-05-21T12:00:00",
        }
    )
    assert "text" in payload
    assert "blocks" in payload
    assert "Drop" in payload["text"]
    assert "AAPL" in payload["text"]


@patch.dict("os.environ", {"ALERT_WEBHOOK_FORMAT": "slack"}, clear=False)
def test_from_alert_uses_env_payload_format() -> None:
    notifier = WebhookNotifier.from_alert(
        {"id": "a1", "webhook_url": "https://example.com/hook", "notifications": ["webhook"]}
    )
    assert notifier is not None
    assert notifier._payload_format == "slack"


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_posts_slack_payload(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 200
    notifier = WebhookNotifier("https://example.com/hook", payload_format="slack")
    assert notifier.send({"alert_id": "x", "alert_name": "Test", "symbols": ["AAPL"]}) is True
    payload = mock_post.call_args[1]["json"]
    assert "text" in payload
    assert "blocks" in payload


def test_build_payload_discord_format() -> None:
    notifier = WebhookNotifier("https://example.com/hook", payload_format="discord")
    payload = notifier.build_payload(
        {
            "alert_id": "x",
            "alert_name": "Drop",
            "symbols": ["AAPL"],
            "condition_type": "price_threshold",
            "timestamp": "2026-05-21T12:00:00",
            "test": True,
        }
    )
    assert payload == {
        "content": (
            "**MarketHelm alert (test):** Drop\n"
            "**Symbols:** AAPL\n"
            "**Condition:** price_threshold\n"
            "**Time (UTC):** 2026-05-21T12:00:00"
        )
    }


@patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/x/y"}, clear=False)
def test_from_alert_falls_back_to_discord_env_url() -> None:
    n = WebhookNotifier.from_alert({"id": "a1", "notifications": ["webhook"]})
    assert n is not None
    assert n._url == "https://discord.com/api/webhooks/x/y"


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_posts_discord_payload(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 204
    notifier = WebhookNotifier("https://discord.com/api/webhooks/x/y", payload_format="discord")
    assert notifier.send({"alert_id": "x", "alert_name": "Test", "symbols": ["AAPL"]}) is True
    payload = mock_post.call_args[1]["json"]
    assert "content" in payload
    assert "Test" in payload["content"]
    assert "AAPL" in payload["content"]


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_logs_on_http_error(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "err"
    notifier = WebhookNotifier("https://example.com/hook")
    with patch("src.alerts.notifiers.delivery_retry.time.sleep"):
        assert notifier.send({"alert_id": "x"}) is False
    assert mock_post.call_count == 3


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_retries_then_succeeds(mock_post: MagicMock) -> None:
    failing = MagicMock(status_code=503, text="busy")
    success = MagicMock(status_code=200, text="")
    mock_post.side_effect = [failing, success]
    notifier = WebhookNotifier("https://example.com/hook")
    with patch("src.alerts.notifiers.delivery_retry.time.sleep"):
        assert notifier.send({"alert_id": "x"}) is True
    assert mock_post.call_count == 2


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_does_not_retry_client_error(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 403
    mock_post.return_value.text = "forbidden"
    notifier = WebhookNotifier("https://example.com/hook")
    assert notifier.send({"alert_id": "x"}) is False
    mock_post.assert_called_once()


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_returns_false_on_request_error(mock_post: MagicMock) -> None:
    mock_post.side_effect = requests.RequestException("timeout")
    notifier = WebhookNotifier("https://example.com/hook")
    with patch("src.alerts.notifiers.delivery_retry.time.sleep"):
        assert notifier.send({"alert_id": "x"}) is False
    assert mock_post.call_count == 3
