"""try_claim_trigger / restore_trigger_claim must stay per-tenant.

Tenants commonly share alert ids (everyone watches AAPL). A missing
user_id filter on the claim SELECT would treat a sibling's later stamp
as this tenant's previous fire and skip a first delivery. Dropping
user_id from restore DELETE/UPDATE would roll back every tenant that
claimed the same alert_id at the same quote tick — reopening cooldown
or erasing a successful send. Existing claim tests are single-tenant.
"""

from __future__ import annotations

import pytest

from src.storage.alert_watches import (
    get_last_triggered,
    restore_trigger_claim,
    try_claim_trigger,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "trigger-claim-tenant.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_try_claim_trigger_does_not_see_sibling_tenant_timestamp(db) -> None:
    """User A's first claim must succeed even if user B already fired later."""
    user_a = create_user("claim-tenant-a@example.com", "password123")["id"]
    user_b = create_user("claim-tenant-b@example.com", "password123")["id"]

    claimed_b, previous_b = try_claim_trigger(
        user_b, "aapl-low", "2026-07-24T20:00:00+00:00"
    )
    assert claimed_b is True
    assert previous_b is None

    claimed_a, previous_a = try_claim_trigger(
        user_a, "aapl-low", "2026-07-24T12:00:00+00:00"
    )

    assert claimed_a is True
    assert previous_a is None
    assert get_last_triggered(user_a, "aapl-low") == "2026-07-24T12:00:00+00:00"
    assert get_last_triggered(user_b, "aapl-low") == "2026-07-24T20:00:00+00:00"


def test_restore_delete_does_not_remove_sibling_tenant_row(db) -> None:
    """First-claim restore DELETE must not drop a sibling's same-tick row."""
    user_a = create_user("restore-del-a@example.com", "password123")["id"]
    user_b = create_user("restore-del-b@example.com", "password123")["id"]
    tick = "2026-07-24T12:00:00+00:00"

    assert try_claim_trigger(user_b, "aapl-low", tick)[0] is True
    claimed_a, previous_a = try_claim_trigger(user_a, "aapl-low", tick)
    assert claimed_a is True
    assert previous_a is None

    restore_trigger_claim(user_a, "aapl-low", previous_a, claimed_at=tick)

    assert get_last_triggered(user_a, "aapl-low") is None
    assert get_last_triggered(user_b, "aapl-low") == tick


def test_restore_update_does_not_rewrite_sibling_tenant_row(db) -> None:
    """Retry restore UPDATE must not revert a sibling's same-tick claim."""
    user_a = create_user("restore-upd-a@example.com", "password123")["id"]
    user_b = create_user("restore-upd-b@example.com", "password123")["id"]
    first = "2026-07-24T10:00:00+00:00"
    later = "2026-07-24T12:00:00+00:00"

    assert try_claim_trigger(user_a, "aapl-low", first)[0] is True
    assert try_claim_trigger(user_b, "aapl-low", first)[0] is True
    claimed_a, previous_a = try_claim_trigger(user_a, "aapl-low", later)
    claimed_b, previous_b = try_claim_trigger(user_b, "aapl-low", later)
    assert claimed_a is True and previous_a == first
    assert claimed_b is True and previous_b == first

    restore_trigger_claim(user_a, "aapl-low", previous_a, claimed_at=later)

    assert get_last_triggered(user_a, "aapl-low") == first
    assert get_last_triggered(user_b, "aapl-low") == later
