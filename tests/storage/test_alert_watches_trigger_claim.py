"""try_claim_trigger / restore_trigger_claim must fail closed and roll back."""

from datetime import datetime, timedelta, timezone

import pytest

from src.storage.alert_watches import (
    get_last_triggered,
    restore_trigger_claim,
    try_claim_trigger,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "trigger-claim.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("trigger-claim@example.com", "password123")["id"]


def test_first_claim_succeeds_and_records_event_timestamp(db_user) -> None:
    claimed, previous = try_claim_trigger(
        db_user, "aapl-low", "2026-07-24T12:00:00+00:00"
    )
    assert claimed is True
    assert previous is None
    assert get_last_triggered(db_user, "aapl-low") == "2026-07-24T12:00:00+00:00"


def test_same_or_older_event_loses_claim(db_user) -> None:
    try_claim_trigger(db_user, "aapl-low", "2026-07-24T12:00:00+00:00")

    same, previous = try_claim_trigger(
        db_user, "aapl-low", "2026-07-24T12:00:00+00:00"
    )
    older, _ = try_claim_trigger(db_user, "aapl-low", "2026-07-24T11:00:00+00:00")

    assert same is False
    assert older is False
    assert previous == "2026-07-24T12:00:00+00:00"
    assert get_last_triggered(db_user, "aapl-low") == "2026-07-24T12:00:00+00:00"


def test_missing_event_timestamp_fails_closed_when_prior_delivery_exists(
    db_user,
) -> None:
    try_claim_trigger(db_user, "aapl-low", "2026-07-24T12:00:00+00:00")

    claimed, previous = try_claim_trigger(db_user, "aapl-low", timestamp=None)

    assert claimed is False
    assert previous == "2026-07-24T12:00:00+00:00"
    assert get_last_triggered(db_user, "aapl-low") == "2026-07-24T12:00:00+00:00"


@pytest.mark.parametrize("bad_ts", ["", "   ", "not-a-timestamp", "zzzz"])
def test_unparseable_event_timestamp_fails_closed_when_prior_exists(
    db_user, bad_ts
) -> None:
    try_claim_trigger(db_user, "aapl-low", "2026-07-24T12:00:00+00:00")

    claimed, previous = try_claim_trigger(db_user, "aapl-low", bad_ts)

    assert claimed is False
    assert previous == "2026-07-24T12:00:00+00:00"
    assert get_last_triggered(db_user, "aapl-low") == "2026-07-24T12:00:00+00:00"


def test_corrupt_previous_timestamp_fails_closed(db_user) -> None:
    """Poisoned trigger rows must not fail open and allow another send."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alert_trigger_state (user_id, alert_id, last_triggered_at)
            VALUES (?, ?, ?)
            """,
            (db_user, "aapl-low", "zzzz"),
        )

    claimed, previous = try_claim_trigger(
        db_user, "aapl-low", "2026-07-24T13:00:00+00:00"
    )

    assert claimed is False
    assert previous == "zzzz"
    assert get_last_triggered(db_user, "aapl-low") == "zzzz"


def test_cooldown_blocks_newer_event_while_window_is_open(db_user) -> None:
    now = datetime.now(timezone.utc)
    last = (now - timedelta(minutes=5)).isoformat()
    newer = now.isoformat()
    try_claim_trigger(db_user, "aapl-low", last)

    blocked, previous = try_claim_trigger(
        db_user, "aapl-low", newer, cooldown_minutes=60
    )

    assert blocked is False
    assert previous == last
    assert get_last_triggered(db_user, "aapl-low") == last


def test_newer_event_claims_after_cooldown_window(db_user) -> None:
    now = datetime.now(timezone.utc)
    last = (now - timedelta(hours=2)).isoformat()
    newer = now.isoformat()
    try_claim_trigger(db_user, "aapl-low", last)

    allowed, previous = try_claim_trigger(
        db_user, "aapl-low", newer, cooldown_minutes=60
    )

    assert allowed is True
    assert previous == last
    assert get_last_triggered(db_user, "aapl-low") == newer


def test_restore_deletes_row_when_there_was_no_previous_trigger(db_user) -> None:
    claimed, previous = try_claim_trigger(
        db_user, "aapl-low", "2026-07-24T12:00:00+00:00"
    )
    assert claimed is True
    assert previous is None

    restore_trigger_claim(db_user, "aapl-low", previous)

    assert get_last_triggered(db_user, "aapl-low") is None
    retried, _ = try_claim_trigger(db_user, "aapl-low", "2026-07-24T12:00:01+00:00")
    assert retried is True


def test_restore_puts_previous_timestamp_back_for_retry(db_user) -> None:
    try_claim_trigger(db_user, "aapl-low", "2026-07-24T10:00:00+00:00")
    claimed, previous = try_claim_trigger(
        db_user, "aapl-low", "2026-07-24T12:00:00+00:00"
    )
    assert claimed is True
    assert previous == "2026-07-24T10:00:00+00:00"

    restore_trigger_claim(db_user, "aapl-low", previous)

    assert get_last_triggered(db_user, "aapl-low") == "2026-07-24T10:00:00+00:00"
    retried, _ = try_claim_trigger(db_user, "aapl-low", "2026-07-24T12:00:00+00:00")
    assert retried is True
