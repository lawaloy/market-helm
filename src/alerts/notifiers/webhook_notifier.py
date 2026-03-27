"""
POST alert events to an HTTPS webhook (Slack-compatible, Discord, or custom).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from ...core.logger import setup_logger

logger = setup_logger("alerts.webhook")


class WebhookNotifier:
    """Send JSON alert payloads via HTTP POST."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self._url = url
        self._timeout = timeout

    @classmethod
    def from_alert(cls, alert: Dict[str, Any]) -> Optional["WebhookNotifier"]:
        url = alert.get("webhook_url") or os.environ.get("ALERT_WEBHOOK_URL")
        if not url or not str(url).strip():
            logger.warning(
                "Webhook notifier requested but no URL: set 'webhook_url' on the alert "
                "or ALERT_WEBHOOK_URL in the environment."
            )
            return None
        return cls(url=str(url).strip())

    def send(self, event: Dict[str, Any]) -> None:
        try:
            response = requests.post(
                self._url,
                json=event,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Webhook returned %s for alert %s: %s",
                    response.status_code,
                    event.get("alert_id"),
                    response.text[:500],
                )
        except requests.RequestException as exc:
            logger.warning(
                "Webhook delivery failed for alert %s: %s",
                event.get("alert_id"),
                exc,
            )
