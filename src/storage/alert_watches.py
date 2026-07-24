"""Normalized alert watches synced from Helmtower config (multi-user mode)."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.utils.tickers import normalize_ticker

from .database import get_connection

MAX_DELIVERY_LOG = 100


class InvalidAlertWatchConfig(ValueError):
    """Raised when a user alert config cannot be normalized into watch rows."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_threshold(raw_value: Any, alert_id: str) -> Optional[float]:
    if raw_value is None:
        return None
    try:
        threshold = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise InvalidAlertWatchConfig(
            f"Alert '{alert_id}' has an invalid price threshold value."
        ) from exc
    if not math.isfinite(threshold):
        raise InvalidAlertWatchConfig(
            f"Alert '{alert_id}' has an invalid price threshold value."
        )
    return threshold


def _coerce_cooldown(raw_value: Any, alert_id: str) -> int:
    try:
        return int(raw_value or 0)
    except (TypeError, ValueError) as exc:
        raise InvalidAlertWatchConfig(
            f"Alert '{alert_id}' has an invalid cooldown_minutes value."
        ) from exc


def _rows_from_config(user_id: str, config: Dict[str, Any], updated_at: str) -> List[tuple]:
    if not isinstance(config, dict):
        raise InvalidAlertWatchConfig("Alerts config must be an object.")
    defaults = config.get("defaults") or {}
    alerts = config.get("alerts") or []
    rows: List[tuple] = []

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        alert_id = str(alert.get("id") or "").strip()
        if not alert_id:
            continue
        condition = alert.get("condition") or {}
        if not isinstance(condition, dict):
            condition = {}
        condition_type = str(condition.get("type") or "unknown")
        symbol = None
        operator = None
        threshold = None
        if condition_type == "price_threshold":
            # Strip whitespace / reject None-NaN sentinels so watch index keys match quotes.
            symbol = normalize_ticker(condition.get("symbol"))
            operator = condition.get("operator")
            threshold = _coerce_threshold(condition.get("value"), alert_id)
        cooldown_minutes = _coerce_cooldown(alert.get("cooldown_minutes"), alert_id)
        rows.append(
            (
                user_id,
                alert_id,
                1 if alert.get("enabled", False) else 0,
                condition_type,
                symbol,
                operator,
                threshold,
                json.dumps(alert),
                json.dumps(defaults),
                cooldown_minutes,
                updated_at,
            )
        )
    return rows


def validate_watches_config(user_id: str, config: Dict[str, Any]) -> None:
    """Validate that a config can be normalized without mutating watch rows."""
    _rows_from_config(user_id, config, _utc_now())


def sync_watches_from_config(user_id: str, config: Dict[str, Any]) -> None:
    """Replace user's watch rows from a Helmtower alerts config payload."""
    rows = _rows_from_config(user_id, config, _utc_now())

    with get_connection() as conn:
        conn.execute("DELETE FROM alert_watches WHERE user_id = ?", (user_id,))
        if rows:
            conn.executemany(
                """
                INSERT INTO alert_watches (
                    user_id, alert_id, enabled, condition_type, symbol, operator,
                    threshold, alert_json, defaults_json, cooldown_minutes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )


def list_enabled_symbols() -> List[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT symbol FROM alert_watches
            WHERE enabled = 1 AND symbol IS NOT NULL AND symbol != ''
            ORDER BY symbol
            """
        ).fetchall()
    return [
        key
        for key in (normalize_ticker(row["symbol"]) for row in rows)
        if key
    ]


def list_watches_for_symbol(symbol: str) -> List[Dict[str, Any]]:
    normalized = normalize_ticker(symbol)
    if not normalized:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id, alert_id, alert_json, defaults_json, cooldown_minutes,
                   condition_type, operator, threshold
            FROM alert_watches
            WHERE enabled = 1 AND symbol = ?
            """,
            (normalized,),
        ).fetchall()
    watches: List[Dict[str, Any]] = []
    for row in rows:
        watches.append(
            {
                "user_id": row["user_id"],
                "alert_id": row["alert_id"],
                "alert": json.loads(row["alert_json"]),
                "defaults": json.loads(row["defaults_json"]),
                "cooldown_minutes": int(row["cooldown_minutes"] or 0),
                "condition_type": row["condition_type"],
                "operator": row["operator"],
                "threshold": row["threshold"],
            }
        )
    return watches


def get_watch(user_id: str, alert_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT alert_json, defaults_json, cooldown_minutes
            FROM alert_watches WHERE user_id = ? AND alert_id = ?
            """,
            (user_id, alert_id),
        ).fetchone()
    if not row:
        return None
    return {
        "alert": json.loads(row["alert_json"]),
        "defaults": json.loads(row["defaults_json"]),
        "cooldown_minutes": int(row["cooldown_minutes"] or 0),
    }


def get_last_triggered(user_id: str, alert_id: str) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_triggered_at FROM alert_trigger_state WHERE user_id = ? AND alert_id = ?",
            (user_id, alert_id),
        ).fetchone()
    if not row:
        return None
    return row["last_triggered_at"]


def record_trigger(user_id: str, alert_id: str, timestamp: Optional[str] = None) -> None:
    ts = timestamp or _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alert_trigger_state (user_id, alert_id, last_triggered_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, alert_id) DO UPDATE SET last_triggered_at = excluded.last_triggered_at
            """,
            (user_id, alert_id, ts),
        )


def record_delivery(
    user_id: str,
    alert_id: str,
    channel: str,
    *,
    success: bool,
    test: bool = False,
    error: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> None:
    ts = timestamp or _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alert_delivery_log (user_id, alert_id, channel, success, test, error, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, alert_id, channel, 1 if success else 0, 1 if test else 0, error, ts),
        )
        count_row = conn.execute(
            "SELECT COUNT(*) AS n FROM alert_delivery_log WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        excess = int(count_row["n"]) - MAX_DELIVERY_LOG
        if excess > 0:
            conn.execute(
                """
                DELETE FROM alert_delivery_log
                WHERE id IN (
                    SELECT id FROM alert_delivery_log
                    WHERE user_id = ?
                    ORDER BY timestamp ASC, id ASC
                    LIMIT ?
                )
                """,
                (user_id, excess),
            )


def latest_trigger_timestamp_for_user(user_id: str) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(last_triggered_at) AS ts
            FROM alert_trigger_state
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row or not row["ts"]:
        return None
    return str(row["ts"])


def latest_deliveries_for_user(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT alert_id, channel, success, test, error, timestamp
            FROM alert_delivery_log
            WHERE user_id = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (user_id, MAX_DELIVERY_LOG),
        ).fetchall()
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        channel = row["channel"]
        if channel in latest:
            continue
        latest[channel] = {
            "alert_id": row["alert_id"],
            "channel": channel,
            "success": bool(row["success"]),
            "test": bool(row["test"]),
            "timestamp": row["timestamp"],
            "error": row["error"],
        }
    return [latest[key] for key in sorted(latest.keys())]
