"""Non-finite delivery retry env vars must not crash or unbounded-sleep."""

from unittest.mock import MagicMock, patch

import pytest

from src.alerts.notifiers.delivery_retry import (
    DEFAULT_BASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_SECONDS,
    DeliveryAttempt,
    deliver_with_retry,
    resolve_delivery_retry_settings,
)


@pytest.mark.parametrize(
    "env",
    [
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "inf",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "8",
        },
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "1e999",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "8",
        },
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "nan",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "8",
        },
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "1",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "inf",
        },
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "1",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "-inf",
        },
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "inf",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "inf",
        },
        {
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "NaN",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "Infinity",
        },
    ],
)
def test_resolve_delivery_retry_settings_rejects_nonfinite_floats(env: dict) -> None:
    with patch.dict(
        "os.environ",
        {"ALERT_DELIVERY_MAX_ATTEMPTS": "3", **env},
        clear=True,
    ):
        settings = resolve_delivery_retry_settings()

    assert settings.max_attempts == DEFAULT_MAX_ATTEMPTS
    # Non-finite sides fall back to defaults; finite "1" / "8" stay parsed.
    base_raw = env["ALERT_DELIVERY_RETRY_BASE_SECONDS"]
    max_raw = env["ALERT_DELIVERY_RETRY_MAX_SECONDS"]
    assert settings.base_seconds == (
        1.0 if base_raw == "1" else DEFAULT_BASE_SECONDS
    )
    assert settings.max_seconds == (
        8.0 if max_raw == "8" else DEFAULT_MAX_SECONDS
    )


@patch("src.alerts.notifiers.delivery_retry.time.sleep")
def test_deliver_with_retry_never_sleeps_nonfinite_when_env_is_inf(
    mock_sleep: MagicMock,
) -> None:
    """Regression: float('inf') used to reach time.sleep and raise OverflowError."""
    with patch.dict(
        "os.environ",
        {
            "ALERT_DELIVERY_MAX_ATTEMPTS": "3",
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": "inf",
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": "inf",
        },
        clear=True,
    ):
        attempt = MagicMock(
            side_effect=[
                DeliveryAttempt(ok=False, retriable=True),
                DeliveryAttempt(ok=True),
            ]
        )
        assert deliver_with_retry(
            operation="Test",
            alert_id="a1",
            attempt=attempt,
        )

    assert attempt.call_count == 2
    assert mock_sleep.call_count == 1
    delay = mock_sleep.call_args[0][0]
    assert delay == DEFAULT_BASE_SECONDS
