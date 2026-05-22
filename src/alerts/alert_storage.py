"""
Alert history storage.
"""

from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import json


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
            return {"last_triggered": {}, "events": []}
        try:
            with open(self.history_path, "r") as f:
                return json.load(f)
        except Exception:
            return {"last_triggered": {}, "events": []}

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

    def record_event(self, event: Dict) -> None:
        history = self._load()
        history.setdefault("events", []).append(event)
        history.setdefault("last_triggered", {})[event["alert_id"]] = event["timestamp"]
        self._save(history)

    def latest_event_timestamp(self) -> Optional[str]:
        history = self._load()
        events = history.get("events") or []
        if not events:
            return None
        return events[-1].get("timestamp")
