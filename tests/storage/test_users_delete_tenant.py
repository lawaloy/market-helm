"""delete_user_account must stay per-tenant.

Account deletion DELETEs the users row (FK cascade then drops that
tenant's configs, watches, tokens, and trigger/delivery rows). Tenants
share one users table. Existing delete tests are single-tenant or use
raw SQL, so a missing id filter would wipe every other account when
one tenant deletes theirs.
"""

from __future__ import annotations

import pytest

from src.storage.alert_watches import get_watch
from src.storage.database import init_database
from src.storage.user_alerts import load_user_alerts_config, save_user_alerts_config
from src.storage.users import (
    authenticate_user,
    create_user,
    delete_user_account,
    get_user_by_id,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "account-delete-tenant.db"
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{db_path.as_posix()}",
    )
    init_database()
    return db_path


def _aapl_config(*, threshold: float, webhook_url: str) -> dict:
    return {
        "defaults": {
            "webhook_url": webhook_url,
            "notify_webhook": True,
        },
        "alerts": [
            {
                "id": "aapl-low",
                "enabled": True,
                "cooldown_minutes": 30,
                "notifications": ["webhook"],
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": threshold,
                },
            }
        ],
    }


def test_delete_user_account_does_not_remove_sibling_tenant(db) -> None:
    """Deleting A must not drop B's row or bump B's session_version."""
    user_a = create_user("account-delete-a@example.com", "password123")
    user_b = create_user("account-delete-b@example.com", "password456")
    assert user_a["session_version"] == 1
    assert user_b["session_version"] == 1

    delete_user_account(user_a["id"], "password123")

    assert get_user_by_id(user_a["id"]) is None
    assert authenticate_user("account-delete-a@example.com", "password123") is None
    loaded_b = get_user_by_id(user_b["id"])
    authed_b = authenticate_user("account-delete-b@example.com", "password456")
    assert loaded_b is not None and authed_b is not None
    assert loaded_b["id"] == user_b["id"]
    assert loaded_b["session_version"] == 1
    assert authed_b["id"] == user_b["id"]
    assert authed_b["session_version"] == 1
    assert authenticate_user("account-delete-b@example.com", "password123") is None


def test_delete_user_account_does_not_cascade_sibling_watches(db) -> None:
    """FK cascade for A must not drop B's same alert_id config or watch."""
    user_a = create_user("delete-watch-a@example.com", "password123")["id"]
    user_b = create_user("delete-watch-b@example.com", "password456")["id"]
    save_user_alerts_config(
        user_a, _aapl_config(threshold=150, webhook_url="https://hooks.example/a")
    )
    save_user_alerts_config(
        user_b, _aapl_config(threshold=50, webhook_url="https://hooks.example/b")
    )

    delete_user_account(user_a, "password123")

    exists_b, config_b = load_user_alerts_config(user_b)
    watch_b = get_watch(user_b, "aapl-low")
    assert exists_b is True
    assert config_b is not None
    assert config_b["alerts"][0]["condition"]["value"] == 50
    assert config_b["defaults"]["webhook_url"] == "https://hooks.example/b"
    assert watch_b is not None
    assert watch_b["alert"]["condition"]["value"] == 50
    assert watch_b["defaults"]["webhook_url"] == "https://hooks.example/b"
    exists_a, _ = load_user_alerts_config(user_a)
    assert exists_a is False
    assert get_watch(user_a, "aapl-low") is None
