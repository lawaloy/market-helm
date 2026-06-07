"""Tests for scheduled alert worker."""

from unittest.mock import patch

from src.alerts import alert_worker


def test_resolve_interval_seconds_explicit_minimum() -> None:
    assert alert_worker.resolve_interval_seconds(30) == 60
    assert alert_worker.resolve_interval_seconds(120) == 120


def test_resolve_interval_seconds_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_CHECK_INTERVAL_SECONDS", "180")
    assert alert_worker.resolve_interval_seconds() == 180


def test_resolve_interval_seconds_invalid_env_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_CHECK_INTERVAL_SECONDS", "not-a-number")
    assert alert_worker.resolve_interval_seconds() == alert_worker.DEFAULT_INTERVAL_SECONDS


def test_resolve_interval_seconds_default_without_env(monkeypatch) -> None:
    monkeypatch.delenv("ALERT_CHECK_INTERVAL_SECONDS", raising=False)
    assert alert_worker.resolve_interval_seconds() == alert_worker.DEFAULT_INTERVAL_SECONDS


@patch("src.alerts.alert_worker.run_check_once")
def test_run_worker_once_logs_trigger(mock_run, caplog) -> None:
    mock_run.return_value = {
        "triggered": 1,
        "last_data_date": "2026-05-20",
        "events": [{"alert_name": "AAPL drop", "symbols": ["AAPL"]}],
    }
    with caplog.at_level("INFO"):
        result = alert_worker.run_worker_once()
    assert result["triggered"] == 1
    assert "triggered 1 watch" in caplog.text


@patch("src.alerts.alert_worker.run_check_once")
def test_run_worker_once_logs_no_data_message(mock_run, caplog) -> None:
    mock_run.return_value = {
        "triggered": 0,
        "last_data_date": None,
        "message": "No market data available.",
    }
    with caplog.at_level("INFO"):
        alert_worker.run_worker_once()
    assert "No market data available." in caplog.text


@patch("src.alerts.alert_worker.time.sleep")
@patch("src.alerts.alert_worker.run_worker_once")
def test_run_worker_loop_stops_via_callback(mock_once, _mock_sleep, caplog) -> None:
    with caplog.at_level("INFO"):
        alert_worker.run_worker_loop(60, should_stop=lambda: True)
    assert mock_once.call_count == 1
    assert "Alert worker stopped" in caplog.text


@patch("src.alerts.alert_worker.signal.signal")
@patch("src.alerts.alert_worker.time.sleep")
@patch("src.alerts.alert_worker.time.monotonic")
@patch("src.alerts.alert_worker.run_worker_once")
def test_run_worker_loop_repeats_until_stop_callback(
    mock_once, mock_monotonic, _mock_sleep, mock_signal
) -> None:
    """The daemon path should continue evaluating after an interval until asked to stop."""
    mock_monotonic.side_effect = [0, 0, 61, 61, 61]
    stop_checks = iter([False, True])

    alert_worker.run_worker_loop(60, should_stop=lambda: next(stop_checks))

    assert mock_once.call_count == 2
    assert mock_signal.call_count == 2
