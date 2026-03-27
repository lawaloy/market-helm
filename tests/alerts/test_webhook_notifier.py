"""Tests for webhook alert delivery."""

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.webhook_notifier import WebhookNotifier


def test_from_alert_returns_none_without_url() -> None:
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
    notifier.send(event)
    mock_post.assert_called_once()
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == event
    assert kwargs["timeout"] == 10.0


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_send_logs_on_http_error(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "err"
    notifier = WebhookNotifier("https://example.com/hook")
    notifier.send({"alert_id": "x"})
