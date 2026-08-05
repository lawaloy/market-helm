"""Regression: concurrent hosted config saves must not drop webhook secrets."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.storage.database import init_database
from src.storage.user_alerts import load_user_alerts_config, save_user_alerts_config
from src.storage.users import create_user

SECRET = "https://hooks.example/user/secret-token"
NEW = "https://hooks.example/user/rotated-token"


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "webhook-rmw.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("webhook-rmw@example.com", "password123")["id"]


def test_concurrent_blank_preserve_cannot_clobber_rotated_secret(db_user) -> None:
    """Blank-secret preserve racing a rotation must not revive the old secret.

    Without BEGIN IMMEDIATE around load→merge→write, a blank update can load
    the pre-rotation row, then overwrite the rotated URL after the rotator
    commits — silently restoring the stale webhook secret.
    """
    save_user_alerts_config(
        db_user,
        {"defaults": {"webhook_url": SECRET, "notify_webhook": True}, "alerts": []},
    )

    barrier = threading.Barrier(2)
    n = 40

    def rotate_secret() -> None:
        barrier.wait(timeout=5)
        save_user_alerts_config(
            db_user,
            {
                "defaults": {"webhook_url": NEW, "notify_webhook": True},
                "alerts": [],
            },
        )

    def blank_preserve() -> None:
        barrier.wait(timeout=5)
        for index in range(n):
            save_user_alerts_config(
                db_user,
                {
                    "defaults": {
                        "webhook_url": "",
                        "notify_webhook": True,
                        "email_to": f"ops{index}@example.com",
                    },
                    "alerts": [],
                },
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(rotate_secret), pool.submit(blank_preserve)]
        for future in futures:
            future.result(timeout=30)

    _, raw = load_user_alerts_config(db_user)
    assert raw is not None
    # Blank preserve must merge from the committed row under the write lock, so
    # once NEW is stored it cannot be rolled back to SECRET or cleared.
    assert raw["defaults"]["webhook_url"] == NEW
    assert raw["defaults"]["email_to"] == f"ops{n - 1}@example.com"


def test_concurrent_distinct_default_updates_preserve_rotated_secret(db_user) -> None:
    """Two writers racing distinct non-secret fields keep the rotated webhook."""
    save_user_alerts_config(
        db_user,
        {"defaults": {"webhook_url": SECRET}, "alerts": []},
    )

    barrier = threading.Barrier(2)

    def writer_a() -> None:
        barrier.wait(timeout=5)
        for index in range(30):
            save_user_alerts_config(
                db_user,
                {
                    "defaults": {
                        "webhook_url": "",
                        "email_to": f"a{index}@example.com",
                    },
                    "alerts": [],
                },
            )

    def writer_b() -> None:
        barrier.wait(timeout=5)
        save_user_alerts_config(
            db_user,
            {"defaults": {"webhook_url": NEW, "cooldown_minutes": 15}, "alerts": []},
        )
        for index in range(30):
            save_user_alerts_config(
                db_user,
                {
                    "defaults": {
                        "webhook_url": "",
                        "cooldown_minutes": 15,
                        "email_to": f"b{index}@example.com",
                    },
                    "alerts": [],
                },
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer_a), pool.submit(writer_b)]
        for future in futures:
            future.result(timeout=30)

    _, raw = load_user_alerts_config(db_user)
    assert raw is not None
    assert raw["defaults"]["webhook_url"] == NEW
    assert raw["defaults"]["email_to"].endswith("@example.com")
