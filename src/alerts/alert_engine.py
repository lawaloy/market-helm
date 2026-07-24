"""
Core alert engine.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json

from ..core.logger import setup_logger
from .alert_paths import apply_alert_defaults, resolve_alerts_config_path
from .alert_storage import AlertStorage
from .alert_rules import evaluate_price_threshold, evaluate_screening_match
from .delivery_status import record_notifier_delivery
from .notifiers.email_notifier import EmailNotifier
from .notifiers.webhook_notifier import WebhookNotifier
from src.utils.tickers import normalize_ticker

logger = setup_logger("alerts")


class LogNotifier:
    def send(self, event: Dict) -> bool:
        logger.info(
            f"Alert triggered: {event['alert_name']} ({event['alert_id']}) "
            f"symbols={event.get('symbols', [])}"
        )
        return True


NOTIFIERS = {
    "log": LogNotifier,
}


class AlertEngine:
    def __init__(
        self,
        alerts: List[Dict],
        storage: Optional[AlertStorage] = None,
        defaults: Optional[Dict[str, Any]] = None,
    ):
        self.alerts = alerts
        self.storage = storage or AlertStorage()
        self.defaults = defaults or {}

    @staticmethod
    def from_config_dict(
        config: Dict[str, Any],
        storage: Optional[AlertStorage] = None,
    ) -> Optional["AlertEngine"]:
        defaults = config.get("defaults") or {}
        alerts = config.get("alerts", [])
        enabled = [alert for alert in alerts if alert.get("enabled", False)]
        if not enabled:
            return None
        return AlertEngine(enabled, storage=storage, defaults=defaults)

    @staticmethod
    def from_config(config_path: Optional[Path] = None) -> Optional["AlertEngine"]:
        config_path = resolve_alerts_config_path(config_path)
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load alerts config: {e}")
            return None
        return AlertEngine.from_config_dict(config)

    def deliver_event(self, alert: Dict, event: Dict) -> bool:
        """Send notifications for a matched watch (used by the delivery job worker)."""
        delivered = False
        is_test = bool(event.get("test"))
        for notifier in self._build_notifiers(alert):
            try:
                result = notifier.send(event)
            except Exception as exc:
                logger.warning(
                    "Notifier %s failed for alert %s: %s",
                    notifier.__class__.__name__,
                    alert["id"],
                    exc,
                )
                record_notifier_delivery(
                    self.storage,
                    alert_id=alert["id"],
                    notifier=notifier,
                    success=False,
                    test=is_test,
                    error=str(exc),
                )
                continue
            success = result is not False
            record_notifier_delivery(
                self.storage,
                alert_id=alert["id"],
                notifier=notifier,
                success=success,
                test=is_test,
            )
            if success:
                delivered = True

        if not delivered:
            return False

        self.storage.record_event(event)
        return True

    def _within_cooldown(self, alert: Dict) -> bool:
        try:
            cooldown_minutes = int(alert.get("cooldown_minutes", 0) or 0)
        except (TypeError, ValueError):
            # File-mode configs may carry junk cooldown values; treat as no cooldown
            # so one bad alert cannot abort evaluation of sibling watches.
            logger.warning(
                "Invalid cooldown_minutes on alert %s; treating as 0",
                alert.get("id"),
            )
            return False
        if cooldown_minutes <= 0:
            return False
        last_triggered = self.storage.get_last_triggered(alert["id"])
        if not last_triggered:
            return False
        now = (
            datetime.now(last_triggered.tzinfo)
            if last_triggered.tzinfo
            else datetime.utcnow()
        )
        return now - last_triggered < timedelta(minutes=cooldown_minutes)

    def _build_notifiers(self, alert: Dict) -> List[Any]:
        alert = apply_alert_defaults(alert, self.defaults)
        notifier_names = alert.get("notifications") or ["log"]
        instances: List[Any] = []
        for name in notifier_names:
            if name == "log":
                instances.append(LogNotifier())
            elif name == "webhook":
                webhook = WebhookNotifier.from_alert(alert)
                if webhook:
                    instances.append(webhook)
            elif name == "email":
                email = EmailNotifier.from_alert(alert)
                if email:
                    instances.append(email)
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
                symbol = normalize_ticker(condition.get("symbol"))
                if not symbol:
                    continue
                stock = next(
                    (
                        s
                        for s in stocks
                        if normalize_ticker(s.get("symbol")) == symbol
                    ),
                    None,
                )
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

            if not self.deliver_event(alert, event):
                logger.warning(
                    "Alert %s matched but no notifications were delivered; "
                    "leaving it eligible for retry.",
                    alert["id"],
                )
                continue

            events.append(event)

        return events
