"""Per-user Helmtower alert configuration in SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.alerts.alert_paths import polish_alerts_config

from .database import get_connection
from .alert_watches import validate_watches_config

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


def _merge_existing_webhook_secrets(
    user_id: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    _, existing = load_user_alerts_config(user_id)
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


def load_user_alerts_config(user_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Return (exists, config). config is None when the user has no row yet.

    Corrupt / non-object JSON soft-fails to (True, None) so Settings GET can
    recover instead of 500ing — mirrors file-mode load_alerts_config.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT config_json FROM user_alert_configs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return False, None
    try:
        data = json.loads(row["config_json"])
    except (TypeError, json.JSONDecodeError):
        return True, None
    if not isinstance(data, dict):
        return True, None
    return True, data


def save_user_alerts_config(user_id: str, config: Dict[str, Any]) -> None:
    # In hosted DB mode webhook URLs are per-user secrets. They are stripped only
    # from API responses, not from persisted user records used for delivery.
    payload = polish_alerts_config(
        _merge_existing_webhook_secrets(user_id, config),
        seed_env_email=False,
    )
    validate_watches_config(user_id, payload)
    updated_at = datetime.now(timezone.utc).isoformat()
    blob = json.dumps(payload, indent=2)
    with get_connection() as conn:
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
    from .alert_watches import sync_watches_from_config

    sync_watches_from_config(user_id, payload)


def init_user_alerts_config(user_id: str, *, force: bool = False) -> None:
    exists, _ = load_user_alerts_config(user_id)
    if exists and not force:
        raise FileExistsError(f"Alerts config already exists for user {user_id}")
    save_user_alerts_config(user_id, dict(_EMPTY_CONFIG))
