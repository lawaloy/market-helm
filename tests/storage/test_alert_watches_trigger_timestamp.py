"""record_trigger must store only parseable cooldown markers."""

from datetime import datetime, timedelta, timezone

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import JOB_DELIVER, JOB_EVALUATE_SYMBOL, enqueue_job, pending_job_count
from src.storage.alert_watches import get_last_triggered, record_trigger, sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "trigger-ts.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("trigger-ts@example.com", "password123")
    return user["id"]


def _watch_config(cooldown_minutes: int = 60):
    return {
        "defaults": {},
        "alerts": [
            {
                "id": "aapl-low",
                "name": "AAPL low",
                "enabled": True,
                "cooldown_minutes": cooldown_minutes,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
                "notifiers": [{"type": "console"}],
            }
        ],
    }


@pytest.mark.parametrize(
    "bad_ts",
    [None, "", "   ", "not-a-timestamp", "2026-13-99T99:99:99Z", "yesterday"],
)
def test_record_trigger_falls_back_to_utc_now_for_unusable_timestamps(db_user, bad_ts) -> None:
    before = datetime.now(timezone.utc)
    record_trigger(db_user, "aapl-low", timestamp=bad_ts)
    raw = get_last_triggered(db_user, "aapl-low")
    assert raw is not None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    assert abs((parsed - before).total_seconds()) < 5


def test_record_trigger_preserves_valid_iso_timestamps(db_user) -> None:
    record_trigger(db_user, "aapl-low", timestamp="2026-07-24T12:00:00Z")
    assert get_last_triggered(db_user, "aapl-low") == "2026-07-24T12:00:00Z"


def test_corrupt_trigger_timestamp_does_not_disable_cooldown(db_user) -> None:
    """Unparseable event stamps must not leave cooldown fail-open."""
    sync_watches_from_config(db_user, _watch_config(cooldown_minutes=60))
    record_trigger(db_user, "aapl-low", timestamp="garbage-ts")
    enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0})

    stats = process_job_queue("trigger-ts-worker")
    assert stats["evaluated"] == 1
    assert stats["failed"] == 0
    assert pending_job_count([JOB_DELIVER]) == 0


def test_overwrite_valid_marker_with_corrupt_keeps_parseable_state(db_user) -> None:
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    record_trigger(db_user, "aapl-low", timestamp=old)
    record_trigger(db_user, "aapl-low", timestamp="not-a-timestamp")

    raw = get_last_triggered(db_user, "aapl-low")
    assert raw is not None
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # Fallback is "now", not the unusable string and not stuck on the old value forever.
    assert abs((parsed - datetime.now(timezone.utc)).total_seconds()) < 5
