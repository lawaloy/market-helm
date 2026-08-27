"""record_trigger must stay per-tenant for a shared alert_id.

Tenants commonly share alert ids (everyone watches AAPL). record_trigger
UPSERTs last_triggered_at and is the hosted AlertEngine write path
(UserAlertStorage.record_event). Existing tests use distinct ids (#500)
or try_claim_trigger (#503), so a missing user_id on the conflict target
would overwrite a sibling's cooldown stamp for the same alert_id.
"""

from __future__ import annotations

import pytest

from src.storage.alert_watches import get_last_triggered, record_trigger
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "record-trigger-tenant.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_record_trigger_does_not_overwrite_sibling_same_alert_id(db) -> None:
    """Recording A for aapl-low must not rewrite B's stamp for the same id."""
    user_a = create_user("record-trigger-a@example.com", "password123")["id"]
    user_b = create_user("record-trigger-b@example.com", "password123")["id"]

    record_trigger(user_b, "aapl-low", timestamp="2026-07-24T10:00:00+00:00")
    record_trigger(user_a, "aapl-low", timestamp="2026-07-24T12:00:00+00:00")
    record_trigger(user_a, "aapl-low", timestamp="2026-07-24T14:00:00+00:00")

    assert get_last_triggered(user_a, "aapl-low") == "2026-07-24T14:00:00+00:00"
    assert get_last_triggered(user_b, "aapl-low") == "2026-07-24T10:00:00+00:00"


def test_record_trigger_does_not_create_sibling_row(db) -> None:
    """A first fire for A must not insert a trigger row for empty tenant B."""
    user_a = create_user("record-empty-a@example.com", "password123")["id"]
    user_b = create_user("record-empty-b@example.com", "password123")["id"]

    record_trigger(user_a, "aapl-low", timestamp="2026-07-24T12:00:00+00:00")

    assert get_last_triggered(user_a, "aapl-low") == "2026-07-24T12:00:00+00:00"
    assert get_last_triggered(user_b, "aapl-low") is None
