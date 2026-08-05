"""File-mode AlertStorage must store only parseable cooldown / delivery stamps."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.alerts.alert_engine import AlertEngine
from src.alerts.alert_storage import AlertStorage


@pytest.mark.parametrize(
    "bad_ts",
    [None, "", "   ", "not-a-timestamp", "2026-13-99T99:99:99Z", "yesterday"],
)
def test_record_event_falls_back_to_utc_now_for_unusable_timestamps(
    tmp_path: Path, bad_ts
) -> None:
    storage = AlertStorage(tmp_path)
    before = datetime.now(timezone.utc)
    storage.record_event({"alert_id": "a1", "timestamp": bad_ts})

    got = storage.get_last_triggered("a1")
    assert got is not None
    if got.tzinfo is None:
        got = got.replace(tzinfo=timezone.utc)
    assert abs((got - before).total_seconds()) < 5
    assert storage.latest_event_timestamp() is not None


def test_record_event_preserves_valid_iso_timestamps(tmp_path: Path) -> None:
    storage = AlertStorage(tmp_path)
    storage.record_event({"alert_id": "a1", "timestamp": "2026-07-24T12:00:00Z"})
    assert storage.get_last_triggered("a1") == datetime(
        2026, 7, 24, 12, 0, tzinfo=timezone.utc
    )
    assert storage.latest_event_timestamp() == "2026-07-24T12:00:00Z"


def test_corrupt_trigger_timestamp_does_not_disable_cooldown(tmp_path: Path) -> None:
    """Unparseable event stamps must not leave file-mode cooldown fail-open."""
    storage = AlertStorage(tmp_path)
    storage.record_event({"alert_id": "aapl-low", "timestamp": "garbage-ts"})

    engine = AlertEngine(
        [
            {
                "id": "aapl-low",
                "name": "AAPL low",
                "enabled": True,
                "cooldown_minutes": 60,
                "notifications": ["log"],
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
            }
        ],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])
    assert events == []


@pytest.mark.parametrize(
    "bad_ts",
    [None, "", "   ", "not-a-timestamp", "zzzz", "2026-13-99T99:99:99Z"],
)
def test_record_delivery_falls_back_to_utc_now_for_unusable_timestamps(
    tmp_path: Path, bad_ts
) -> None:
    storage = AlertStorage(tmp_path)
    before = datetime.now(timezone.utc)
    storage.record_delivery(
        alert_id="a1",
        channel="email",
        success=True,
        timestamp=bad_ts,
    )
    latest = storage.latest_delivery_by_channel()
    assert len(latest) == 1
    parsed = datetime.fromisoformat(str(latest[0]["timestamp"]).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    assert abs((parsed - before).total_seconds()) < 5


def test_record_delivery_preserves_valid_iso_timestamps(tmp_path: Path) -> None:
    storage = AlertStorage(tmp_path)
    storage.record_delivery(
        alert_id="a1",
        channel="webhook",
        success=True,
        timestamp="2026-07-24T13:00:00+00:00",
    )
    latest = storage.latest_delivery_by_channel()
    assert latest[0]["timestamp"] == "2026-07-24T13:00:00+00:00"
