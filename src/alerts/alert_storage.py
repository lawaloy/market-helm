"""
Alert history storage.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

MAX_DELIVERY_LOG = 100


def _empty_history() -> Dict[str, Any]:
    return {"last_triggered": {}, "events": [], "delivery_log": []}


class AlertStorage:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent.parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.data_dir / "alerts_history.json"

    def _load(self) -> Dict:
        if not self.history_path.exists():
            return _empty_history()
        try:
            with open(self.history_path, "r") as f:
                data = json.load(f)
        except Exception:
            return _empty_history()
        if not isinstance(data, dict):
            return _empty_history()
        last_triggered = data.get("last_triggered")
        if not isinstance(last_triggered, dict):
            last_triggered = {}
        events = data.get("events")
        if not isinstance(events, list):
            events = []
        delivery_log = data.get("delivery_log")
        if not isinstance(delivery_log, list):
            delivery_log = []
        return {
            "last_triggered": last_triggered,
            "events": events,
            "delivery_log": delivery_log,
        }

    def _save(self, history: Dict) -> None:
        with open(self.history_path, "w") as f:
            json.dump(history, f, indent=2)

    def get_last_triggered(self, alert_id: str) -> Optional[datetime]:
        history = self._load()
        last_ts = history.get("last_triggered", {}).get(alert_id)
        if not last_ts:
            return None
        try:
            return datetime.fromisoformat(last_ts)
        except Exception:
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
        history = self._load()
        entry: Dict[str, Any] = {
            "alert_id": alert_id,
            "channel": channel,
            "success": success,
            "test": test,
            "timestamp": timestamp or datetime.utcnow().isoformat(),
        }
        if error:
            entry["error"] = error[:500]
        delivery_log = history.setdefault("delivery_log", [])
        delivery_log.append(entry)
        if len(delivery_log) > MAX_DELIVERY_LOG:
            history["delivery_log"] = delivery_log[-MAX_DELIVERY_LOG:]
        self._save(history)

    def latest_delivery_by_channel(self) -> List[Dict[str, Any]]:
        """Most recent delivery attempt per channel (email, webhook)."""
        history = self._load()
        delivery_log = history.get("delivery_log") or []
        latest: Dict[str, Dict[str, Any]] = {}
        for entry in reversed(delivery_log):
            if not isinstance(entry, dict):
                continue
            channel = entry.get("channel")
            if not channel or channel in latest:
                continue
            latest[channel] = entry
        return [latest[key] for key in sorted(latest.keys())]

    def record_event(self, event: Dict) -> None:
        history = self._load()
        history.setdefault("events", []).append(event)
        history.setdefault("last_triggered", {})[event["alert_id"]] = event["timestamp"]
        self._save(history)

    def latest_event_timestamp(self) -> Optional[str]:
        history = self._load()
        events = history.get("events") or []
        for entry in reversed(events):
            if not isinstance(entry, dict):
                continue
            timestamp = entry.get("timestamp")
            if timestamp:
                return timestamp
        return None
