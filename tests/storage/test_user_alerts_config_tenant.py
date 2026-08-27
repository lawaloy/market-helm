"""save/load_user_alerts_config must stay per-tenant.

Hosted Settings save load→merge→write webhook secrets from the existing
row, then syncs watches in the same transaction. A missing user_id on
the config SELECT would copy a sibling's webhook URL into this tenant
(or overwrite their JSON). Existing preserve tests are single-tenant;
watch-index isolation is covered separately via sync_watches_from_config.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from src.storage.alert_watches import get_watch, list_watches_for_symbol
from src.storage.database import init_database
from src.storage.user_alerts import (
    load_user_alerts_config,
    save_user_alerts_config,
)
from src.storage.users import create_user

WEBHOOK_A = "https://hooks.example/a"
WEBHOOK_B = "https://hooks.example/b"
GLOBAL_MAILBOX = "global-shared@example.com"


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts-config-tenant.db"
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
    email_to: str | None = None,
    alert_id: str = "aapl-low",
) -> dict:
    defaults: dict = {
        "webhook_url": webhook_url,
        "notify_webhook": True,
    }
    if email_to is not None:
        defaults["email_to"] = email_to
    return {
        "defaults": defaults,
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


def _webhook_host(url: str) -> str | None:
    return urlparse(url).hostname


def test_load_does_not_return_sibling_tenant_config(db) -> None:
    """Shared alert ids must not leak another tenant's webhook or threshold."""
    user_a = create_user("config-tenant-a@example.com", "password123")["id"]
    user_b = create_user("config-tenant-b@example.com", "password123")["id"]

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

    exists_a, loaded_a = load_user_alerts_config(user_a)
    exists_b, loaded_b = load_user_alerts_config(user_b)
    assert exists_a is True and exists_b is True
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alerts"][0]["condition"]["value"] == 150
    assert loaded_a["defaults"]["webhook_url"] == WEBHOOK_A
    assert loaded_a["defaults"]["email_to"] == "a@example.com"
    assert loaded_b["alerts"][0]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == WEBHOOK_B
    assert loaded_b["defaults"]["email_to"] == "b@example.com"
    webhook_a = loaded_a["defaults"]["webhook_url"]
    webhook_b = loaded_b["defaults"]["webhook_url"]
    assert _webhook_host(webhook_a) == "hooks.example"
    assert webhook_a != webhook_b
    assert GLOBAL_MAILBOX not in str(loaded_a)
    assert GLOBAL_MAILBOX not in str(loaded_b)

    watch_a = get_watch(user_a, "aapl-low")
    watch_b = get_watch(user_b, "aapl-low")
    assert watch_a is not None and watch_b is not None
    assert watch_a["defaults"]["webhook_url"] == WEBHOOK_A
    assert watch_b["defaults"]["webhook_url"] == WEBHOOK_B


def test_blank_webhook_save_does_not_copy_sibling_secret(db) -> None:
    """Blank webhook must keep this tenant's secret, not a sibling's."""
    user_a = create_user("config-merge-a@example.com", "password123")["id"]
    user_b = create_user("config-merge-b@example.com", "password123")["id"]

    save_user_alerts_config(
        user_a,
        _price_config(threshold=150, webhook_url=WEBHOOK_A),
    )
    save_user_alerts_config(
        user_b,
        _price_config(threshold=50, webhook_url=WEBHOOK_B),
    )

    save_user_alerts_config(
        user_a,
        _price_config(threshold=25, webhook_url=""),
    )

    _, loaded_a = load_user_alerts_config(user_a)
    _, loaded_b = load_user_alerts_config(user_b)
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alerts"][0]["condition"]["value"] == 25
    assert loaded_a["defaults"]["webhook_url"] == WEBHOOK_A
    assert loaded_b["defaults"]["webhook_url"] == WEBHOOK_B
    assert loaded_b["alerts"][0]["condition"]["value"] == 50
    assert GLOBAL_MAILBOX not in str(loaded_a)
    assert GLOBAL_MAILBOX not in str(loaded_b)

    watch_a = get_watch(user_a, "aapl-low")
    watch_b = get_watch(user_b, "aapl-low")
    assert watch_a is not None and watch_b is not None
    assert watch_a["defaults"]["webhook_url"] == WEBHOOK_A
    assert watch_a["alert"]["condition"]["value"] == 25
    assert watch_b["defaults"]["webhook_url"] == WEBHOOK_B
    assert watch_b["alert"]["condition"]["value"] == 50


def test_save_does_not_overwrite_sibling_config(db) -> None:
    """Replacing user A's Settings must not rewrite user B's same alert_id."""
    user_a = create_user("config-replace-a@example.com", "password123")["id"]
    user_b = create_user("config-replace-b@example.com", "password123")["id"]

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

    save_user_alerts_config(user_a, {"defaults": {}, "alerts": []})

    exists_a, loaded_a = load_user_alerts_config(user_a)
    exists_b, loaded_b = load_user_alerts_config(user_b)
    assert exists_a is True and exists_b is True
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["alerts"] == []
    assert loaded_a["defaults"].get("email_to") != GLOBAL_MAILBOX
    assert loaded_b["alerts"][0]["condition"]["value"] == 50
    assert loaded_b["defaults"]["webhook_url"] == WEBHOOK_B
    assert loaded_b["defaults"]["email_to"] == "b@example.com"
    assert get_watch(user_a, "aapl-low") is None
    watch_b = get_watch(user_b, "aapl-low")
    assert watch_b is not None
    assert watch_b["defaults"]["webhook_url"] == WEBHOOK_B
    watches = list_watches_for_symbol("AAPL")
    remaining = {(w["user_id"], w["alert_id"]) for w in watches}
    assert remaining == {(user_b, "aapl-low")}
