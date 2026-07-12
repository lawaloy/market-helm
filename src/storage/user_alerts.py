"""Per-user Helmtower alert configuration in SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.alerts.alert_paths import polish_alerts_config, strip_webhook_secrets_from_config

from .database import get_connection
from .alert_watches import validate_watches_config

_EMPTY_CONFIG: Dict[str, Any] = {"defaults": {}, "alerts": []}


def load_user_alerts_config(user_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Return (exists, config). config is None when the user has no row yet."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT config_json FROM user_alert_configs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return False, None
    return True, json.loads(row["config_json"])


def save_user_alerts_config(user_id: str, config: Dict[str, Any]) -> None:
    payload = strip_webhook_secrets_from_config(polish_alerts_config(config))
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
