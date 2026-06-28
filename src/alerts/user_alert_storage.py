"""User-scoped AlertStorage adapter for multi-user DB mode."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.storage import alert_watches as db_watches


class UserAlertStorage:
    """Per-user cooldown + delivery history in SQLite."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_last_triggered(self, alert_id: str) -> Optional[datetime]:
        raw = db_watches.get_last_triggered(self.user_id, alert_id)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def record_delivery(
        self,
        *,
        alert_id: str,
        channel: str,
        success: bool,
        test: bool = False,
        error: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        db_watches.record_delivery(
            self.user_id,
            alert_id,
            channel,
            success=success,
            test=test,
            error=error,
            timestamp=timestamp,
        )

    def record_event(self, event: Dict[str, Any]) -> None:
        db_watches.record_trigger(
            self.user_id,
            str(event["alert_id"]),
            timestamp=event.get("timestamp"),
        )

    def latest_delivery_by_channel(self) -> List[Dict[str, Any]]:
        return db_watches.latest_deliveries_for_user(self.user_id)

    def latest_event_timestamp(self) -> Optional[str]:
        return db_watches.latest_trigger_timestamp_for_user(self.user_id)
