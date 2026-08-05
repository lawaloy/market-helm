"""Per-user Helmtower alert configuration in SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.alerts.alert_paths import polish_alerts_config

from .database import get_connection
from .alert_watches import sync_watches_from_config, validate_watches_config

_EMPTY_CONFIG: Dict[str, Any] = {"defaults": {}, "alerts": []}


def _copy_webhook_secret_if_missing(
    target: Dict[str, Any],
    existing: Dict[str, Any],
) -> None:
    if str(target.get("webhook_url") or "").strip():
        target["webhook_url"] = str(target["webhook_url"]).strip()
        return
    existing_url = str(existing.get("webhook_url") or "").strip()
    if existing_url:
        target["webhook_url"] = existing_url


def _parse_config_json(raw: Any) -> Optional[Dict[str, Any]]:
    """Decode a stored config blob; corrupt / non-object → None (soft-fail)."""
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _merge_existing_webhook_secrets(
    config: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not existing:
        return config

    merged = dict(config)
    raw_defaults = merged.get("defaults")
    defaults = dict(raw_defaults) if isinstance(raw_defaults, dict) else {}
    existing_defaults = existing.get("defaults")
    if not isinstance(existing_defaults, dict):
        existing_defaults = {}
    _copy_webhook_secret_if_missing(defaults, existing_defaults)
    merged["defaults"] = defaults

    existing_alerts = {
        str(alert.get("id")): alert
        for alert in existing.get("alerts") or []
        if isinstance(alert, dict) and alert.get("id")
    }
    alerts = []
    for alert in merged.get("alerts") or []:
        if not isinstance(alert, dict):
            alerts.append(alert)
            continue
        copied = dict(alert)
        existing_alert = existing_alerts.get(str(copied.get("id")))
        if existing_alert:
            _copy_webhook_secret_if_missing(copied, existing_alert)
        alerts.append(copied)
    merged["alerts"] = alerts
    return merged


def _load_config_row(
    conn: sqlite3.Connection, user_id: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    row = conn.execute(
        "SELECT config_json FROM user_alert_configs WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return False, None
    return True, _parse_config_json(row["config_json"])


def load_user_alerts_config(user_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Return (exists, config). config is None when the user has no row yet.

    Corrupt / non-object JSON soft-fails to (True, None) so Settings GET can
    recover instead of 500ing — mirrors file-mode load_alerts_config.
    """
    with get_connection() as conn:
        return _load_config_row(conn, user_id)


def save_user_alerts_config(user_id: str, config: Dict[str, Any]) -> None:
    # In hosted DB mode webhook URLs are per-user secrets. They are stripped only
    # from API responses, not from persisted user records used for delivery.
    # BEGIN IMMEDIATE serializes load→merge→write so a blank-secret preserve
    # cannot clobber a concurrent non-blank webhook rotation (lost secret).
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _, existing = _load_config_row(conn, user_id)
        payload = polish_alerts_config(
            _merge_existing_webhook_secrets(config, existing),
            seed_env_email=False,
        )
        validate_watches_config(user_id, payload)
        updated_at = datetime.now(timezone.utc).isoformat()
        blob = json.dumps(payload, indent=2)
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                config_json = excluded.config_json,
                updated_at = excluded.updated_at
            """,
            (user_id, blob, updated_at),
        )
        sync_watches_from_config(user_id, payload, connection=conn)


def init_user_alerts_config(user_id: str, *, force: bool = False) -> None:
    exists, _ = load_user_alerts_config(user_id)
    if exists and not force:
        raise FileExistsError(f"Alerts config already exists for user {user_id}")
    save_user_alerts_config(user_id, dict(_EMPTY_CONFIG))
