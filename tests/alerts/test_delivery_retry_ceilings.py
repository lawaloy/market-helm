"""Extreme finite retry env values must clamp to safe worker ceilings."""

from unittest.mock import MagicMock, patch

import pytest

from src.alerts.notifiers.delivery_retry import (
    MAX_ATTEMPTS_CEILING,
    MAX_BASE_SECONDS_CEILING,
    MAX_SECONDS_CEILING,
    DeliveryAttempt,
    deliver_with_retry,
    resolve_delivery_retry_settings,
)


@patch.dict(
    "os.environ",
    {
        "ALERT_DELIVERY_MAX_ATTEMPTS": "100000000",
        "ALERT_DELIVERY_RETRY_BASE_SECONDS": "999999",
        "ALERT_DELIVERY_RETRY_MAX_SECONDS": "1e12",
    },
    clear=True,
)
def test_resolve_delivery_retry_settings_clamps_extreme_finite_values() -> None:
    settings = resolve_delivery_retry_settings()
    assert settings.max_attempts == MAX_ATTEMPTS_CEILING
    assert settings.base_seconds == MAX_BASE_SECONDS_CEILING
    assert settings.max_seconds == MAX_SECONDS_CEILING


@pytest.mark.parametrize(
    ("attempts", "base", "max_s"),
    [
        ("10", "60", "300"),
        ("5", "1", "8"),
    ],
)
def test_resolve_delivery_retry_settings_accepts_values_at_or_below_ceiling(
    attempts: str, base: str, max_s: str
) -> None:
    with patch.dict(
        "os.environ",
        {
            "ALERT_DELIVERY_MAX_ATTEMPTS": attempts,
            "ALERT_DELIVERY_RETRY_BASE_SECONDS": base,
            "ALERT_DELIVERY_RETRY_MAX_SECONDS": max_s,
        },
        clear=True,
    ):
        settings = resolve_delivery_retry_settings()
    assert settings.max_attempts == int(attempts)
    assert settings.base_seconds == float(base)
    assert settings.max_seconds == float(max_s)


@patch("src.alerts.notifiers.delivery_retry.time.sleep")
@patch.dict(
    "os.environ",
    {
        "ALERT_DELIVERY_MAX_ATTEMPTS": "100000000",
        "ALERT_DELIVERY_RETRY_BASE_SECONDS": "999999",
        "ALERT_DELIVERY_RETRY_MAX_SECONDS": "1e12",
    },
    clear=True,
)
def test_deliver_with_retry_honors_clamped_ceilings(mock_sleep: MagicMock) -> None:
    """Poisoned env must not exceed attempt/delay ceilings during retries."""
    attempt = MagicMock(return_value=DeliveryAttempt(ok=False, retriable=True))
    settings = resolve_delivery_retry_settings()

    assert (
        deliver_with_retry(
            operation="Test",
            alert_id="a1",
            attempt=attempt,
            settings=settings,
        )
        is False
    )

    assert attempt.call_count == MAX_ATTEMPTS_CEILING
    assert mock_sleep.call_count == MAX_ATTEMPTS_CEILING - 1
    for call in mock_sleep.call_args_list:
        delay = call.args[0]
        assert 0.0 <= delay <= MAX_SECONDS_CEILING
