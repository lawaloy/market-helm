"""ALERT_CHECK_INTERVAL_SECONDS / --interval must not sleep the worker forever."""

import pytest

from src.alerts import alert_worker


def test_resolve_interval_seconds_clamps_extreme_explicit() -> None:
    assert (
        alert_worker.resolve_interval_seconds(10**18)
        == alert_worker.MAX_INTERVAL_SECONDS
    )
    assert (
        alert_worker.resolve_interval_seconds(alert_worker.MAX_INTERVAL_SECONDS)
        == alert_worker.MAX_INTERVAL_SECONDS
    )
    assert alert_worker.resolve_interval_seconds(120) == 120


def test_resolve_interval_seconds_clamps_extreme_env(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_CHECK_INTERVAL_SECONDS", "1000000000000")
    assert alert_worker.resolve_interval_seconds() == alert_worker.MAX_INTERVAL_SECONDS

    monkeypatch.setenv(
        "ALERT_CHECK_INTERVAL_SECONDS", str(alert_worker.MAX_INTERVAL_SECONDS)
    )
    assert alert_worker.resolve_interval_seconds() == alert_worker.MAX_INTERVAL_SECONDS


@pytest.mark.parametrize("raw", ["30", "1"])
def test_resolve_interval_seconds_still_enforces_minimum(monkeypatch, raw: str) -> None:
    monkeypatch.setenv("ALERT_CHECK_INTERVAL_SECONDS", raw)
    assert alert_worker.resolve_interval_seconds() == alert_worker.MIN_INTERVAL_SECONDS
