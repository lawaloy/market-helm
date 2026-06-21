"""Tests for alert delivery retry/backoff."""

from unittest.mock import MagicMock, patch

from src.alerts.notifiers.delivery_retry import (
    DeliveryAttempt,
    DeliveryRetrySettings,
    deliver_with_retry,
    is_retriable_http_status,
    resolve_delivery_retry_settings,
)


def test_is_retriable_http_status() -> None:
    assert is_retriable_http_status(429) is True
    assert is_retriable_http_status(500) is True
    assert is_retriable_http_status(503) is True
    assert is_retriable_http_status(404) is False
    assert is_retriable_http_status(403) is False


@patch.dict(
    "os.environ",
    {
        "ALERT_DELIVERY_MAX_ATTEMPTS": "4",
        "ALERT_DELIVERY_RETRY_BASE_SECONDS": "0",
        "ALERT_DELIVERY_RETRY_MAX_SECONDS": "0",
    },
    clear=True,
)
def test_resolve_delivery_retry_settings_from_env() -> None:
    settings = resolve_delivery_retry_settings()
    assert settings.max_attempts == 4
    assert settings.base_seconds == 0.0
    assert settings.max_seconds == 0.0


def test_deliver_with_retry_succeeds_on_first_attempt() -> None:
    attempt = MagicMock(return_value=DeliveryAttempt(ok=True))
    assert deliver_with_retry(
        operation="Test",
        alert_id="a1",
        attempt=attempt,
        settings=DeliveryRetrySettings(max_attempts=3, base_seconds=0, max_seconds=0),
    )
    attempt.assert_called_once()


@patch("src.alerts.notifiers.delivery_retry.time.sleep")
def test_deliver_with_retry_retries_transient_failures(mock_sleep: MagicMock) -> None:
    attempt = MagicMock(
        side_effect=[
            DeliveryAttempt(ok=False, retriable=True),
            DeliveryAttempt(ok=False, retriable=True),
            DeliveryAttempt(ok=True),
        ]
    )
    settings = DeliveryRetrySettings(max_attempts=3, base_seconds=1.0, max_seconds=8.0)

    assert deliver_with_retry(
        operation="Test",
        alert_id="a1",
        attempt=attempt,
        settings=settings,
    )

    assert attempt.call_count == 3
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)


@patch("src.alerts.notifiers.delivery_retry.time.sleep")
def test_deliver_with_retry_stops_on_permanent_failure(mock_sleep: MagicMock) -> None:
    attempt = MagicMock(return_value=DeliveryAttempt(ok=False, retriable=False))

    assert (
        deliver_with_retry(
            operation="Test",
            alert_id="a1",
            attempt=attempt,
            settings=DeliveryRetrySettings(max_attempts=3, base_seconds=1.0, max_seconds=8.0),
        )
        is False
    )

    attempt.assert_called_once()
    mock_sleep.assert_not_called()


@patch("src.alerts.notifiers.delivery_retry.time.sleep")
def test_deliver_with_retry_exhausts_attempts(mock_sleep: MagicMock) -> None:
    attempt = MagicMock(return_value=DeliveryAttempt(ok=False, retriable=True))

    assert (
        deliver_with_retry(
            operation="Test",
            alert_id="a1",
            attempt=attempt,
            settings=DeliveryRetrySettings(max_attempts=3, base_seconds=0, max_seconds=0),
        )
        is False
    )

    assert attempt.call_count == 3
    assert mock_sleep.call_count == 2
