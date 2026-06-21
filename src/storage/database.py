"""SQLite database connection and schema for multi-user mode."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

from src.alerts.alert_paths import user_config_dir

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


def default_database_path() -> Path:
    """Default SQLite path when enabling multi-user locally without a URL."""
    return user_config_dir() / "markethelm.db"
