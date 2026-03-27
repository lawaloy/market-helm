"""
Core alert engine.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json

from ..core.logger import setup_logger
from .alert_storage import AlertStorage
from .alert_rules import evaluate_price_threshold, evaluate_screening_match
from .notifiers.webhook_notifier import WebhookNotifier

logger = setup_logger("alerts")


class LogNotifier:
    def send(self, event: Dict) -> None:
        logger.info(
            f"Alert triggered: {event['alert_name']} ({event['alert_id']}) "
            f"symbols={event.get('symbols', [])}"
        )


NOTIFIERS = {
    "log": LogNotifier,
}


class AlertEngine:
    def __init__(self, alerts: List[Dict], storage: Optional[AlertStorage] = None):
        self.alerts = alerts
        self.storage = storage or AlertStorage()

    @staticmethod
    def from_config(config_path: Optional[Path] = None) -> Optional["AlertEngine"]:
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "alerts.json"
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load alerts config: {e}")
            return None

        alerts = config.get("alerts", [])
        enabled = [alert for alert in alerts if alert.get("enabled", False)]
        if not enabled:
            return None
        return AlertEngine(enabled)

    def _within_cooldown(self, alert: Dict) -> bool:
        cooldown_minutes = int(alert.get("cooldown_minutes", 0))
        if cooldown_minutes <= 0:
            return False
        last_triggered = self.storage.get_last_triggered(alert["id"])
        if not last_triggered:
            return False
        return datetime.utcnow() - last_triggered < timedelta(minutes=cooldown_minutes)

    def _build_notifiers(self, alert: Dict) -> List[Any]:
        notifier_names = alert.get("notifications") or ["log"]
        instances: List[Any] = []
        for name in notifier_names:
            if name == "log":
                instances.append(LogNotifier())
            elif name == "webhook":
                webhook = WebhookNotifier.from_alert(alert)
                if webhook:
                    instances.append(webhook)
            else:
                notifier_cls = NOTIFIERS.get(name)
                if notifier_cls:
                    instances.append(notifier_cls())
                else:
                    logger.warning(f"Unknown notifier '{name}', skipping")
        if not instances:
            instances.append(LogNotifier())
        return instances

    def evaluate(self, stocks: List[Dict]) -> List[Dict]:
        events: List[Dict] = []
        for alert in self.alerts:
            if self._within_cooldown(alert):
                continue

            condition = alert.get("condition", {})
            condition_type = condition.get("type")
            triggered_symbols: List[str] = []

            if condition_type == "price_threshold":
                symbol = condition.get("symbol")
                if not symbol:
                    continue
                stock = next((s for s in stocks if s.get("symbol") == symbol), None)
                if stock and evaluate_price_threshold(condition, stock):
                    triggered_symbols = [symbol]
            elif condition_type == "screening_match":
                for stock in stocks:
                    if evaluate_screening_match(condition, stock):
                        triggered_symbols.append(stock.get("symbol"))
            else:
                logger.warning(f"Unsupported alert condition: {condition_type}")
                continue

            if not triggered_symbols:
                continue

            event = {
                "alert_id": alert["id"],
                "alert_name": alert.get("name", alert["id"]),
                "symbols": triggered_symbols,
                "timestamp": datetime.utcnow().isoformat(),
                "condition_type": condition_type,
            }

            self.storage.record_event(event)
            for notifier in self._build_notifiers(alert):
                notifier.send(event)

            events.append(event)

        return events
