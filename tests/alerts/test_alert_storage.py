"""Tests for alert history storage."""

from src.alerts.alert_storage import AlertStorage


def test_load_corrupt_history_returns_empty(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)
    storage.history_path.write_text("{not-json", encoding="utf-8")

    history = storage._load()

    assert history == {"last_triggered": {}, "events": [], "delivery_log": []}
    assert storage.get_last_triggered("any") is None
    assert storage.latest_event_timestamp() is None


def test_get_last_triggered_returns_none_for_unparseable_iso(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)
    storage.history_path.write_text(
        '{"last_triggered": {"a1": "not-a-timestamp"}, "events": [], "delivery_log": []}',
        encoding="utf-8",
    )

    assert storage.get_last_triggered("a1") is None


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


def test_record_delivery_trims_log(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)
    for index in range(105):
        storage.record_delivery(
            alert_id=f"a{index}",
            channel="email",
            success=True,
            timestamp=f"2026-05-01T12:00:{index:02d}",
        )
    history = storage._load()
    assert len(history["delivery_log"]) == 100
    assert history["delivery_log"][0]["alert_id"] == "a5"
