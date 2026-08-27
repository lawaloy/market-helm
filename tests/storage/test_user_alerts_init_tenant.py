"""init_user_alerts_config must stay per-tenant.

Hosted POST /api/alerts/init load-checks this tenant then saves an empty
config. A missing user_id on the exists SELECT would 409 every new user
once any sibling has Settings, or force-init would wipe that sibling's
JSON and watches. Existing init tests are single-tenant; #505 covers
save/load of already-populated configs, not the empty-tenant onboarding
short-circuit.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from src.storage.alert_watches import get_watch, list_watches_for_symbol
from src.storage.database import init_database
from src.storage.user_alerts import (
    init_user_alerts_config,
    load_user_alerts_config,
    save_user_alerts_config,
)
from src.storage.users import create_user

WEBHOOK_A = "https://hooks.example/a"
WEBHOOK_B = "https://hooks.example/b"
GLOBAL_MAILBOX = "global-shared@example.com"


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts-init-tenant.db"
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{db_path.as_posix()}",
    )
    monkeypatch.setenv("ALERT_EMAIL_TO", GLOBAL_MAILBOX)
    init_database()
    return db_path


def _price_config(
    *,
    threshold: float,
    webhook_url: str,
    email_to: str,
    alert_id: str = "aapl-low",
) -> dict:
    return {
        "defaults": {
            "webhook_url": webhook_url,
            "notify_webhook": True,
            "email_to": email_to,
        },
        "alerts": [
            {
                "id": alert_id,
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


def test_init_does_not_conflict_when_only_sibling_has_config(db) -> None:
    """Empty tenant A must init even when sibling B already has Settings."""
    user_a = create_user("init-tenant-a@example.com", "password123")["id"]
    user_b = create_user("init-tenant-b@example.com", "password123")["id"]

    save_user_alerts_config(
        user_b,
        _price_config(
            threshold=50,
            webhook_url=WEBHOOK_B,
            email_to="b@example.com",
        ),
    )

    exists_a, loaded_a = load_user_alerts_config(user_a)
    assert exists_a is False
    assert loaded_a is None

    init_user_alerts_config(user_a)

    exists_a, loaded_a = load_user_alerts_config(user_a)
    exists_b, loaded_b = load_user_alerts_config(user_b)
    assert exists_a is True and exists_b is True
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alerts"] == []
    assert loaded_a["defaults"].get("email_to") != GLOBAL_MAILBOX
    assert GLOBAL_MAILBOX not in str(loaded_a)
    assert loaded_b["alerts"][0]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == WEBHOOK_B
    assert loaded_b["defaults"]["email_to"] == "b@example.com"
    assert urlparse(loaded_b["defaults"]["webhook_url"]).hostname == "hooks.example"
    assert get_watch(user_a, "aapl-low") is None
    watch_b = get_watch(user_b, "aapl-low")
    assert watch_b is not None
    assert watch_b["defaults"]["webhook_url"] == WEBHOOK_B
    remaining = {(w["user_id"], w["alert_id"]) for w in list_watches_for_symbol("AAPL")}
    assert remaining == {(user_b, "aapl-low")}


def test_force_init_does_not_wipe_sibling_config(db) -> None:
    """force=True must reset this tenant only, not a sibling's same alert_id."""
    user_a = create_user("init-force-a@example.com", "password123")["id"]
    user_b = create_user("init-force-b@example.com", "password123")["id"]

    save_user_alerts_config(
        user_a,
        _price_config(
            threshold=150,
            webhook_url=WEBHOOK_A,
            email_to="a@example.com",
        ),
    )
    save_user_alerts_config(
        user_b,
        _price_config(
            threshold=50,
            webhook_url=WEBHOOK_B,
            email_to="b@example.com",
        ),
    )

    init_user_alerts_config(user_a, force=True)

    exists_a, loaded_a = load_user_alerts_config(user_a)
    exists_b, loaded_b = load_user_alerts_config(user_b)
    assert exists_a is True and exists_b is True
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alerts"] == []
    # Empty-config save still preserves this tenant's secret (same merge as
    # a blank webhook field) and must not copy a sibling's URL.
    assert loaded_a["defaults"].get("webhook_url") == WEBHOOK_A
    assert loaded_a["defaults"].get("webhook_url") != WEBHOOK_B
    assert urlparse(loaded_a["defaults"]["webhook_url"]).hostname == "hooks.example"
    assert GLOBAL_MAILBOX not in str(loaded_a)
    assert loaded_b["alerts"][0]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == WEBHOOK_B
    assert loaded_b["defaults"]["email_to"] == "b@example.com"
    assert get_watch(user_a, "aapl-low") is None
    watch_b = get_watch(user_b, "aapl-low")
    assert watch_b is not None
    assert watch_b["defaults"]["webhook_url"] == WEBHOOK_B
    remaining = {(w["user_id"], w["alert_id"]) for w in list_watches_for_symbol("AAPL")}
    assert remaining == {(user_b, "aapl-low")}
