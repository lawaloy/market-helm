"""SQLite database connection and schema for multi-user mode."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from src.alerts.alert_paths import user_config_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


class MigrationError(RuntimeError):
    """Raised when the configured database cannot be migrated safely."""


_MIGRATIONS = (
    Migration(
        version=1,
        name="initial_multi_user_schema",
        statements=(
            """CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
)""",
            """CREATE TABLE IF NOT EXISTS user_alert_configs (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)""",
            """CREATE TABLE IF NOT EXISTS alert_watches (
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
)""",
            """CREATE INDEX IF NOT EXISTS idx_alert_watches_symbol_enabled
    ON alert_watches(symbol, enabled)""",
            """CREATE TABLE IF NOT EXISTS alert_trigger_state (
    user_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    last_triggered_at TEXT NOT NULL,
    PRIMARY KEY (user_id, alert_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)""",
            """CREATE TABLE IF NOT EXISTS alert_delivery_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    success INTEGER NOT NULL,
    test INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)""",
            """CREATE INDEX IF NOT EXISTS idx_alert_delivery_log_user_ts
    ON alert_delivery_log(user_id, timestamp DESC)""",
            """CREATE TABLE IF NOT EXISTS alert_jobs (
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
)""",
            """CREATE INDEX IF NOT EXISTS idx_alert_jobs_poll
    ON alert_jobs(status, run_after, id)""",
        ),
    ),
)

LATEST_SCHEMA_VERSION = _MIGRATIONS[-1].version

_MIGRATION_TABLE = """CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
)"""


def database_enabled() -> bool:
    return bool((os.environ.get("MARKET_HELM_DATABASE_URL") or "").strip())


def database_backend() -> str:
    """Return the configured storage backend name."""
    raw = (os.environ.get("MARKET_HELM_DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("MARKET_HELM_DATABASE_URL is not set")
    scheme = urlparse(raw).scheme.lower()
    if scheme == "sqlite":
        return "sqlite"
    if scheme in {"postgres", "postgresql"}:
        return "postgresql"
    raise ValueError(
        f"Unsupported database URL scheme {scheme!r}. "
        "Use sqlite:///... or postgresql://..."
    )


def resolve_database_path() -> Path:
    """Resolve SQLite file path from MARKET_HELM_DATABASE_URL (sqlite:///...)."""
    raw = (os.environ.get("MARKET_HELM_DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("MARKET_HELM_DATABASE_URL is not set")
    parsed = urlparse(raw)
    if parsed.scheme != "sqlite":
        raise ValueError(
            f"Expected a sqlite URL (got {parsed.scheme!r}). "
            "Use resolve_database_path() only for SQLite connections."
        )
    # sqlite://host/path silently ignored host before and wrote a local file —
    # fail closed so misconfigured hosted URLs cannot point at the wrong DB.
    if parsed.netloc:
        raise ValueError(
            f"SQLite URL must be a local file path without a host "
            f"(got netloc {parsed.netloc!r}). "
            "Use sqlite:////absolute/path/to/markethelm.db"
        )
    if parsed.path:
        # sqlite:///C:/path or sqlite:////var/lib/db
        path = parsed.path
        if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return Path(path)
    raise ValueError(f"Invalid SQLite URL: {raw!r}")


class _PostgresConnection:
    """Small DB-API compatibility layer for the existing SQLite-style queries."""

    backend = "postgresql"

    def __init__(self, connection: Any):
        self._connection = connection

    @staticmethod
    def _query(sql: str) -> str:
        # Storage SQL uses DB-API qmark placeholders and contains no literal
        # question marks. Psycopg uses the format placeholder style.
        return sql.replace("?", "%s")

    def execute(self, sql: str, params: Any = None) -> Any:
        return self._connection.execute(self._query(sql), params or ())

    def executemany(self, sql: str, params: Any) -> Any:
        cursor = self._connection.cursor()
        return cursor.executemany(self._query(sql), params)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def _connect_sqlite() -> sqlite3.Connection:
    path = resolve_database_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Unwritable / blocked parents must surface as a clear RuntimeError so
        # multi-user auth/alerts paths fail closed with an actionable message
        # instead of an opaque PermissionError from pathlib.
        raise RuntimeError(
            f"Cannot create database directory {path.parent}: {exc}"
        ) from exc
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect_postgresql() -> _PostgresConnection:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires Psycopg with a usable libpq implementation. "
            "Install libpq or psycopg[binary] on a supported platform."
        ) from exc
    raw = (os.environ.get("MARKET_HELM_DATABASE_URL") or "").strip()
    return _PostgresConnection(psycopg.connect(raw, row_factory=dict_row))


@contextmanager
def get_connection() -> Iterator[Any]:
    backend = database_backend()
    conn = _connect_sqlite() if backend == "sqlite" else _connect_postgresql()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migration_statements(backend: str, migration: Migration) -> tuple[str, ...]:
    if backend == "sqlite":
        return migration.statements
    return tuple(
        statement.replace(" UNIQUE COLLATE NOCASE", " UNIQUE").replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY"
        )
        for statement in migration.statements
    )


def apply_migrations(conn: Any) -> None:
    """Apply pending schema migrations atomically and in version order."""
    versions = [migration.version for migration in _MIGRATIONS]
    if versions != list(range(1, LATEST_SCHEMA_VERSION + 1)):
        raise MigrationError("Database migrations must be contiguous and start at version 1")

    try:
        # Serialize startup migrations so concurrent application processes do
        # not both attempt to apply the same version.
        backend = getattr(conn, "backend", "sqlite")
        if backend == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        else:
            conn.execute("SELECT pg_advisory_xact_lock(1296387149)")
        conn.execute(_MIGRATION_TABLE)
        applied_rows = conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        applied = {int(row["version"]) for row in applied_rows}
        unknown = applied.difference(versions)
        if unknown:
            found = ", ".join(str(version) for version in sorted(unknown))
            raise MigrationError(
                "Database schema is newer than this application or contains "
                f"unknown migration versions: {found}"
            )

        for migration in _MIGRATIONS:
            if migration.version in applied:
                continue
            for statement in _migration_statements(backend, migration):
                conn.execute(statement)
            conn.execute(
                """INSERT INTO schema_migrations (version, name, applied_at)
                   VALUES (?, ?, ?)""",
                (
                    migration.version,
                    migration.name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except MigrationError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise MigrationError(f"Failed to apply database migrations: {exc}") from exc


def init_database() -> None:
    if not database_enabled():
        return
    with get_connection() as conn:
        apply_migrations(conn)
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
