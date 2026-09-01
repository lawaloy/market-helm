"""End-to-end storage checks against a real PostgreSQL server."""

from __future__ import annotations

import os
import uuid
from urllib.parse import quote

import psycopg
import pytest

from src.storage.alert_jobs import (
    JOB_EVALUATE_SYMBOL,
    STATUS_COMPLETED,
    claim_jobs,
    complete_job,
    enqueue_job,
)
from src.storage.alert_watches import get_watch
from src.storage.database import get_connection, init_database
from src.storage.rate_limits import consume_rate_limit
from src.storage.account_tokens import RESET_PASSWORD, consume_token, issue_token
from src.storage.health import latest_worker_heartbeat, record_worker_heartbeat
from src.storage.user_alerts import load_user_alerts_config, save_user_alerts_config
from src.storage.users import (
    authenticate_user,
    change_password,
    create_user,
    delete_user_account,
    get_user_by_id,
)


pytestmark = pytest.mark.integration


@pytest.fixture()
def postgresql_database(monkeypatch):
    base_url = os.environ.get("MARKET_HELM_POSTGRES_TEST_URL", "").strip()
    if not base_url:
        raise RuntimeError("MARKET_HELM_POSTGRES_TEST_URL must be configured")

    schema = f"markethelm_test_{uuid.uuid4().hex}"
    with psycopg.connect(base_url, autocommit=True) as admin:
        admin.execute(
            psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
        )

    separator = "&" if "?" in base_url else "?"
    test_url = f"{base_url}{separator}options={quote(f'-csearch_path={schema}') }"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", test_url)
    try:
        yield
    finally:
        with psycopg.connect(base_url, autocommit=True) as admin:
            admin.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(
                    psycopg.sql.Identifier(schema)
                )
            )


def test_postgresql_migrations_and_storage_workflow(postgresql_database):
    init_database()
    user = create_user("postgres@example.com", "correct-horse-battery-staple")
    config = {
        "defaults": {"cooldown_minutes": 15},
        "alerts": [
            {
                "id": "aapl-breakout",
                "enabled": True,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": ">=",
                    "value": 200,
                },
            }
        ],
    }
    save_user_alerts_config(user["id"], config)

    exists, stored = load_user_alerts_config(user["id"])
    watch = get_watch(user["id"], "aapl-breakout")
    assert exists is True
    assert stored is not None
    assert stored["alerts"][0]["id"] == "aapl-breakout"
    assert watch is not None
    assert watch["alert"]["condition"]["symbol"] == "AAPL"

    job_id = enqueue_job(
        JOB_EVALUATE_SYMBOL,
        {"symbol": "AAPL", "price": 201.0},
    )
    claimed = claim_jobs([JOB_EVALUATE_SYMBOL], "postgres-worker", limit=1)
    assert [job["id"] for job in claimed] == [job_id]
    assert complete_job(job_id, worker_id="postgres-worker") is True

    with get_connection() as conn:
        job = conn.execute(
            "SELECT status FROM alert_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        versions = conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    assert job["status"] == STATUS_COMPLETED
    assert [row["version"] for row in versions] == [1, 2, 3, 4, 5]

    reset_token = issue_token(user["id"], RESET_PASSWORD)
    assert consume_token(reset_token, RESET_PASSWORD) == user["id"]
    assert consume_token(reset_token, RESET_PASSWORD) is None

    record_worker_heartbeat("postgres-worker", "healthy", {"delivered": 1})
    heartbeat = latest_worker_heartbeat()
    assert heartbeat is not None
    assert heartbeat["worker_id"] == "postgres-worker"
    assert heartbeat["details"] == {"delivered": 1}

    first_limit = consume_rate_limit("integration:client", now=121, window_seconds=60)
    second_limit = consume_rate_limit("integration:client", now=122, window_seconds=60)
    assert (first_limit.count, second_limit.count, second_limit.reset_at) == (1, 2, 180)

    managed = create_user("managed-postgres@example.com", "password123")
    change_password(managed["id"], "password123", "new-password-123")
    changed = authenticate_user("managed-postgres@example.com", "new-password-123")
    assert changed is not None
    assert changed["session_version"] == 2
    delete_user_account(managed["id"], "new-password-123")
    assert get_user_by_id(managed["id"]) is None
