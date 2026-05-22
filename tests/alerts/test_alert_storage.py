"""Tests for alert history storage."""

from src.alerts.alert_storage import AlertStorage


def test_latest_event_timestamp_empty(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)
    assert storage.latest_event_timestamp() is None


def test_latest_event_timestamp_returns_last(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)
    storage.record_event(
        {"alert_id": "a", "alert_name": "A", "symbols": ["AAPL"], "timestamp": "2026-05-01T12:00:00"}
    )
    storage.record_event(
        {"alert_id": "b", "alert_name": "B", "symbols": ["MSFT"], "timestamp": "2026-05-02T15:30:00"}
    )
    assert storage.latest_event_timestamp() == "2026-05-02T15:30:00"
