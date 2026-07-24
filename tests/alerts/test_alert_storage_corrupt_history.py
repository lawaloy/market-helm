"""Corrupt alerts_history.json must soft-fail instead of AttributeError."""

import json
from pathlib import Path

from src.alerts.alert_storage import AlertStorage


def test_load_non_object_json_returns_empty_history(tmp_path: Path) -> None:
    history = tmp_path / "alerts_history.json"
    history.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    storage = AlertStorage(data_dir=tmp_path)

    data = storage._load()
    assert data == {"last_triggered": {}, "events": [], "delivery_log": []}


def test_load_corrupt_json_returns_empty_history(tmp_path: Path) -> None:
    history = tmp_path / "alerts_history.json"
    history.write_text("{not-json", encoding="utf-8")
    storage = AlertStorage(data_dir=tmp_path)

    assert storage.latest_event_timestamp() is None
    assert storage.latest_delivery_by_channel() == []


def test_record_event_recovers_from_list_root(tmp_path: Path) -> None:
    history = tmp_path / "alerts_history.json"
    history.write_text(json.dumps([]), encoding="utf-8")
    storage = AlertStorage(data_dir=tmp_path)

    storage.record_event(
        {
            "alert_id": "a1",
            "alert_name": "A",
            "symbols": ["AAPL"],
            "timestamp": "2026-07-24T12:00:00",
        }
    )
    assert storage.latest_event_timestamp() == "2026-07-24T12:00:00"
    assert storage.get_last_triggered("a1") is not None


def test_latest_delivery_skips_non_dict_rows(tmp_path: Path) -> None:
    history = tmp_path / "alerts_history.json"
    history.write_text(
        json.dumps(
            {
                "last_triggered": {},
                "events": [],
                "delivery_log": [
                    "junk",
                    None,
                    {
                        "alert_id": "a1",
                        "channel": "email",
                        "success": True,
                        "timestamp": "2026-07-24T10:00:00",
                    },
                    {
                        "alert_id": "a2",
                        "channel": "webhook",
                        "success": False,
                        "timestamp": "2026-07-24T11:00:00",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    storage = AlertStorage(data_dir=tmp_path)

    latest = storage.latest_delivery_by_channel()
    channels = {entry["channel"] for entry in latest}
    assert channels == {"email", "webhook"}


def test_latest_event_skips_trailing_non_dict(tmp_path: Path) -> None:
    history = tmp_path / "alerts_history.json"
    history.write_text(
        json.dumps(
            {
                "last_triggered": {},
                "events": [
                    {
                        "alert_id": "a1",
                        "timestamp": "2026-07-24T09:00:00",
                    },
                    "junk",
                    None,
                ],
                "delivery_log": [],
            }
        ),
        encoding="utf-8",
    )
    storage = AlertStorage(data_dir=tmp_path)
    assert storage.latest_event_timestamp() == "2026-07-24T09:00:00"


def test_load_normalizes_non_list_collections(tmp_path: Path) -> None:
    history = tmp_path / "alerts_history.json"
    history.write_text(
        json.dumps(
            {
                "last_triggered": ["bad"],
                "events": {"not": "a list"},
                "delivery_log": "also-bad",
            }
        ),
        encoding="utf-8",
    )
    storage = AlertStorage(data_dir=tmp_path)
    data = storage._load()
    assert data["last_triggered"] == {}
    assert data["events"] == []
    assert data["delivery_log"] == []
