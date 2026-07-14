"""SQLite database connection and schema for multi-user mode."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

from src.alerts.alert_paths import user_config_dir

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_alert_configs (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_watches (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    condition_type TEXT NOT NULL,
    symbol TEXT,
    operator TEXT,
    threshold REAL,
    alert_json TEXT NOT NULL,
    defaults_json TEXT NOT NULL DEFAULT '{}',
    cooldown_minutes INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, alert_id)
);

CREATE INDEX IF NOT EXISTS idx_alert_watches_symbol_enabled
    ON alert_watches(symbol, enabled);

CREATE TABLE IF NOT EXISTS alert_trigger_state (
    user_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    last_triggered_at TEXT NOT NULL,
    PRIMARY KEY (user_id, alert_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_delivery_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    success INTEGER NOT NULL,
    test INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alert_delivery_log_user_ts
    ON alert_delivery_log(user_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS alert_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    run_after TEXT NOT NULL,
    locked_at TEXT,
    locked_by TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_jobs_poll
    ON alert_jobs(status, run_after, id);
"""


def database_enabled() -> bool:
    return bool((os.environ.get("MARKET_HELM_DATABASE_URL") or "").strip())


def resolve_database_path() -> Path:
    """Resolve SQLite file path from MARKET_HELM_DATABASE_URL (sqlite:///...)."""
    raw = (os.environ.get("MARKET_HELM_DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("MARKET_HELM_DATABASE_URL is not set")
    parsed = urlparse(raw)
    if parsed.scheme != "sqlite":
        raise ValueError(
            f"Only sqlite URLs are supported today (got {parsed.scheme!r}). "
            "Use sqlite:////absolute/path/to/markethelm.db"
        )
    if parsed.path:
        # sqlite:///C:/path or sqlite:////var/lib/db
        path = parsed.path
        if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return Path(path)
    raise ValueError(f"Invalid SQLite URL: {raw!r}")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    path = resolve_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_database() -> None:
    if not database_enabled():
        return
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
    _backfill_watches_from_configs()


def _backfill_watches_from_configs() -> None:
    import json

    from .alert_watches import InvalidAlertWatchConfig
    from .alert_watches import sync_watches_from_config

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, config_json FROM user_alert_configs",
        ).fetchall()
    for row in rows:
        try:
            config = json.loads(row["config_json"])
            sync_watches_from_config(row["user_id"], config)
        except (json.JSONDecodeError, InvalidAlertWatchConfig) as exc:
            logger.warning(
                "Skipping invalid alert config during watch backfill for user %s: %s",
                row["user_id"],
                exc,
            )
            continue


def default_database_path() -> Path:
    """Default SQLite path when enabling multi-user locally without a URL."""
    return user_config_dir() / "markethelm.db"
