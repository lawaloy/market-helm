"""sync_watches_from_config / get_watch must stay per-tenant.

Tenants commonly share alert ids (everyone watches AAPL as aapl-low).
A missing user_id on the replace DELETE would wipe every tenant's watches
on one Settings save. Dropping user_id from get_watch would return a
sibling's webhook URL and threshold. Existing sync tests use distinct
alert ids or never replace after a sibling row exists.
"""

from __future__ import annotations

import pytest

from src.storage.alert_watches import (
    get_watch,
    list_watches_for_symbol,
    sync_watches_from_config,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "watch-sync-tenant.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def _price_config(
    *,
    threshold: float,
    webhook_url: str,
    alert_id: str = "aapl-low",
    enabled: bool = True,
) -> dict:
    return {
        "defaults": {"webhook_url": webhook_url},
        "alerts": [
            {
                "id": alert_id,
                "enabled": enabled,
                "cooldown_minutes": 30,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": threshold,
                },
            }
        ],
    }


def test_get_watch_does_not_return_sibling_tenant_payload(db) -> None:
    """Shared alert ids must not leak another tenant's webhook or threshold."""
    user_a = create_user("sync-tenant-a@example.com", "password123")["id"]
    user_b = create_user("sync-tenant-b@example.com", "password123")["id"]

    sync_watches_from_config(
        user_a,
        _price_config(threshold=150, webhook_url="https://hooks.example/a"),
    )
    sync_watches_from_config(
        user_b,
        _price_config(threshold=50, webhook_url="https://hooks.example/b"),
    )

    loaded_a = get_watch(user_a, "aapl-low")
    loaded_b = get_watch(user_b, "aapl-low")
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alert"]["condition"]["value"] == 150
    assert loaded_a["defaults"]["webhook_url"] == "https://hooks.example/a"
    assert loaded_b["alert"]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == "https://hooks.example/b"
    assert loaded_a["defaults"]["webhook_url"] != loaded_b["defaults"]["webhook_url"]


def test_sync_clear_does_not_delete_sibling_tenant_watch(db) -> None:
    """Empty Settings save must not DELETE another tenant's same alert_id."""
    user_a = create_user("sync-clear-a@example.com", "password123")["id"]
    user_b = create_user("sync-clear-b@example.com", "password123")["id"]

    sync_watches_from_config(
        user_a,
        _price_config(threshold=150, webhook_url="https://hooks.example/a"),
    )
    sync_watches_from_config(
        user_b,
        _price_config(threshold=50, webhook_url="https://hooks.example/b"),
    )

    sync_watches_from_config(user_a, {"defaults": {}, "alerts": []})

    assert get_watch(user_a, "aapl-low") is None
    loaded_b = get_watch(user_b, "aapl-low")
    assert loaded_b is not None
    assert loaded_b["alert"]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == "https://hooks.example/b"
    watches = list_watches_for_symbol("AAPL")
    assert {(w["user_id"], w["alert_id"]) for w in watches} == {(user_b, "aapl-low")}


def test_sync_replace_does_not_rewrite_sibling_tenant_watch(db) -> None:
    """Replacing user A's threshold must not rewrite user B's same alert_id."""
    user_a = create_user("sync-replace-a@example.com", "password123")["id"]
    user_b = create_user("sync-replace-b@example.com", "password123")["id"]

    sync_watches_from_config(
        user_a,
        _price_config(threshold=150, webhook_url="https://hooks.example/a"),
    )
    sync_watches_from_config(
        user_b,
        _price_config(threshold=50, webhook_url="https://hooks.example/b"),
    )

    sync_watches_from_config(
        user_a,
        _price_config(threshold=25, webhook_url="https://hooks.example/a-new"),
    )

    loaded_a = get_watch(user_a, "aapl-low")
    loaded_b = get_watch(user_b, "aapl-low")
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alert"]["condition"]["value"] == 25
    assert loaded_a["defaults"]["webhook_url"] == "https://hooks.example/a-new"
    assert loaded_b["alert"]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == "https://hooks.example/b"
