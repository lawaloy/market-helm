"""Record and query per-channel alert delivery outcomes for the dashboard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .alert_storage import AlertStorage

_CHANNEL_BY_NOTIFIER = {
    "EmailNotifier": "email",
    "WebhookNotifier": "webhook",
}


def notifier_channel_name(notifier: Any) -> Optional[str]:
    """Map a notifier instance to a dashboard channel id, or None for log-only."""
    return _CHANNEL_BY_NOTIFIER.get(notifier.__class__.__name__)


def record_notifier_delivery(
    storage: AlertStorage,
    *,
    alert_id: str,
    notifier: Any,
    success: bool,
    test: bool = False,
    error: Optional[str] = None,
) -> None:
    channel = notifier_channel_name(notifier)
    if not channel:
        return
    storage.record_delivery(
        alert_id=alert_id,
        channel=channel,
        success=success,
        test=test,
        error=error,
    )


def latest_deliveries_by_channel(storage: Optional[AlertStorage] = None) -> List[Dict[str, Any]]:
    store = storage or AlertStorage()
    return store.latest_delivery_by_channel()
