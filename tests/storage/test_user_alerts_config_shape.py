"""Hosted alert configs must soft-fail on non-object JSON and non-dict defaults."""

import json

import pytest

from src.storage.database import get_connection, init_database
from src.storage.user_alerts import load_user_alerts_config, save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "user-alerts-shape.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("shape@example.com", "password123")["id"]


@pytest.mark.parametrize(
    "blob",
    [
        json.dumps(["not", "a", "dict"]),
        json.dumps("token"),
        json.dumps(42),
        json.dumps(None),
        "{not-json",
    ],
)
def test_load_soft_fails_non_object_or_corrupt_json(db_user, blob) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (db_user, blob, "2026-07-24T00:00:00+00:00"),
        )

    exists, raw = load_user_alerts_config(db_user)
    assert exists is True
    assert raw is None


@pytest.mark.parametrize("bad_defaults", [["x"], "ab", 123, True])
def test_save_tolerates_truthy_non_dict_defaults_on_merge(db_user, bad_defaults) -> None:
    """Existing poison defaults must not AttributeError during webhook secret merge."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                db_user,
                json.dumps(
                    {
                        "defaults": bad_defaults,
                        "alerts": [
                            {
                                "id": "keep",
                                "webhook_url": "https://hooks.example/secret",
                            }
                        ],
                    }
                ),
                "2026-07-24T00:00:00+00:00",
            ),
        )

    save_user_alerts_config(
        db_user,
        {
            "defaults": {"email_to": "ops@example.com"},
            "alerts": [{"id": "keep", "enabled": True}],
        },
    )

    exists, raw = load_user_alerts_config(db_user)
    assert exists is True
    assert raw is not None
    assert raw["defaults"]["email_to"] == "ops@example.com"
    # Secret preserved from existing alert row despite poison defaults.
    assert raw["alerts"][0]["webhook_url"] == "https://hooks.example/secret"
