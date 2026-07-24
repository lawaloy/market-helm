"""
POST alert events to an HTTPS webhook (Slack-compatible, Discord, or custom JSON).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from ...core.logger import setup_logger
from .delivery_retry import DeliveryAttempt, deliver_with_retry, is_retriable_http_status

logger = setup_logger("alerts.webhook")


class WebhookNotifier:
    """Send alert payloads via HTTP POST."""

    def __init__(
        self,
        url: str,
        payload_format: str = "json",
        timeout: float = 10.0,
    ) -> None:
        self._url = url
        self._payload_format = payload_format.lower()
        self._timeout = timeout

    @classmethod
    def from_alert(cls, alert: Dict[str, Any]) -> Optional["WebhookNotifier"]:
        from src.storage.database import database_enabled

        allow_env_webhook = alert.get("_allow_env_webhook", not database_enabled()) is not False
        url = (
            alert.get("webhook_url")
            or (os.environ.get("ALERT_WEBHOOK_URL") if allow_env_webhook else None)
            or (os.environ.get("DISCORD_WEBHOOK_URL") if allow_env_webhook else None)
        )
        if not url or not str(url).strip():
            logger.warning(
                "Webhook notifier requested but no URL: set 'webhook_url' on the alert "
                "or ALERT_WEBHOOK_URL in the environment."
            )
            return None
        payload_format = (
            alert.get("webhook_format")
            or alert.get("payload_format")
            or os.environ.get("ALERT_WEBHOOK_FORMAT")
            or "json"
        )
        return cls(url=str(url).strip(), payload_format=str(payload_format).strip().lower())

    @staticmethod
    def _format_symbols(raw: Any) -> str:
        """Join symbol lists for display; tolerate None/non-str junk without TypeError."""
        if raw is None:
            return "(none)"
        if isinstance(raw, str):
            cleaned = raw.strip()
            return cleaned or "(none)"
        if not isinstance(raw, (list, tuple)):
            cleaned = str(raw).strip()
            return cleaned or "(none)"
        parts: list[str] = []
        for item in raw:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                parts.append(text)
        return ", ".join(parts) or "(none)"

    @staticmethod
    def _alert_text(event: Dict[str, Any], markdown: str = "slack") -> str:
        symbols = WebhookNotifier._format_symbols(event.get("symbols"))
        alert_name = event.get("alert_name", event.get("alert_id", "alert"))
        test_label = " (test)" if event.get("test") else ""
        condition = event.get("condition_type", "")
        timestamp = event.get("timestamp", "")
        if markdown == "discord":
            return (
                f"**MarketHelm alert{test_label}:** {alert_name}\n"
                f"**Symbols:** {symbols}\n"
                f"**Condition:** {condition}\n"
                f"**Time (UTC):** {timestamp}"
            )
        return (
            f"*MarketHelm alert{test_label}:* {alert_name}\n"
            f"*Symbols:* {symbols}\n"
            f"*Condition:* {condition}\n"
            f"*Time (UTC):* {timestamp}"
        )

    def build_payload(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if self._payload_format == "slack":
            text = self._alert_text(event, markdown="slack")
            return {
                "text": text,
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": text},
                    }
                ],
            }
        if self._payload_format == "discord":
            return {"content": self._alert_text(event, markdown="discord")}
        return dict(event)

    def _post_once(self, event: Dict[str, Any]) -> DeliveryAttempt:
        payload = self.build_payload(event)
        try:
            response = requests.post(
                self._url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            if response.status_code < 400:
                return DeliveryAttempt(ok=True)
            logger.warning(
                "Webhook returned %s for alert %s: %s",
                response.status_code,
                event.get("alert_id"),
                response.text[:500],
            )
            return DeliveryAttempt(
                ok=False,
                retriable=is_retriable_http_status(response.status_code),
            )
        except requests.RequestException as exc:
            logger.warning(
                "Webhook delivery failed for alert %s: %s",
                event.get("alert_id"),
                exc,
            )
            return DeliveryAttempt(ok=False, retriable=True)

    def send(self, event: Dict[str, Any]) -> bool:
        return deliver_with_retry(
            operation="Webhook",
            alert_id=event.get("alert_id"),
            attempt=lambda: self._post_once(event),
        )
