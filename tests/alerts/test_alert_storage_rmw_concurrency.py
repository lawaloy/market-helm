"""Regression: concurrent file-mode history writers must not drop rows."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from src.alerts.alert_storage import AlertStorage


def test_concurrent_record_delivery_preserves_all_rows(tmp_path):
    """Two AlertStorage instances racing record_delivery keep every entry."""
    barrier = threading.Barrier(2)
    n = 40

    def writer(channel: str) -> None:
        storage = AlertStorage(data_dir=tmp_path)
        barrier.wait(timeout=5)
        for index in range(n):
            storage.record_delivery(
                alert_id=f"{channel}-{index}",
                channel=channel,
                success=True,
                timestamp=f"2026-05-01T12:00:{index:02d}.{channel}",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(writer, "email"),
            pool.submit(writer, "webhook"),
        ]
        for future in futures:
            future.result(timeout=30)

    history = AlertStorage(data_dir=tmp_path)._load()
    delivery_log = history["delivery_log"]
    assert len(delivery_log) == n * 2
    by_channel = {
        "email": {entry["alert_id"] for entry in delivery_log if entry["channel"] == "email"},
        "webhook": {entry["alert_id"] for entry in delivery_log if entry["channel"] == "webhook"},
    }
    assert by_channel["email"] == {f"email-{i}" for i in range(n)}
    assert by_channel["webhook"] == {f"webhook-{i}" for i in range(n)}


def test_concurrent_record_event_preserves_all_rows(tmp_path):
    """Racing record_event calls retain every event and last_triggered key."""
    barrier = threading.Barrier(2)
    n = 30

    def writer(prefix: str) -> None:
        storage = AlertStorage(data_dir=tmp_path)
        barrier.wait(timeout=5)
        for index in range(n):
            alert_id = f"{prefix}-{index}"
            storage.record_event(
                {
                    "alert_id": alert_id,
                    "alert_name": alert_id,
                    "symbols": ["AAPL"],
                    "timestamp": f"2026-05-02T10:{index:02d}:00+00:00",
                }
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(writer, "a"),
            pool.submit(writer, "b"),
        ]
        for future in futures:
            future.result(timeout=30)

    history = AlertStorage(data_dir=tmp_path)._load()
    events = history["events"]
    assert len(events) == n * 2
    event_ids = {entry["alert_id"] for entry in events}
    assert event_ids == {f"a-{i}" for i in range(n)} | {f"b-{i}" for i in range(n)}
    assert set(history["last_triggered"]) == event_ids
