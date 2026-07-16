"""Process evaluate_symbol and deliver jobs from the alert_jobs queue."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from src.alerts.alert_engine import AlertEngine
from src.alerts.alert_rules import evaluate_price_threshold
from src.alerts.user_alert_storage import UserAlertStorage
from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    claim_jobs,
    complete_job,
    enqueue_job,
    fail_job,
    new_worker_id,
)
from src.storage.alert_watches import list_watches_for_symbol
from src.storage.database import init_database

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _event_timestamp(event: Dict[str, Any]) -> datetime | None:
    raw = event.get("timestamp")
    if not raw:
        return None
    try:
        return _as_utc(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
    except ValueError:
        return None


def _within_cooldown(user_id: str, alert_id: str, cooldown_minutes: int) -> bool:
    if cooldown_minutes <= 0:
        return False
    storage = UserAlertStorage(user_id)
    last = storage.get_last_triggered(alert_id)
    if not last:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last < timedelta(minutes=cooldown_minutes)


def _process_evaluate_symbol(job: Dict[str, Any]) -> None:
    payload = job["payload"]
    symbol = str(payload["symbol"]).upper()
    price = float(payload["price"])
    stock = {"symbol": symbol, "close": price}
    triggered = 0

    for watch in list_watches_for_symbol(symbol):
        user_id = watch["user_id"]
        alert_id = watch["alert_id"]
        alert = watch["alert"]
        if _within_cooldown(user_id, alert_id, watch["cooldown_minutes"]):
            continue

        condition = alert.get("condition") or {}
        if watch["condition_type"] != "price_threshold":
            continue
        try:
            matched = evaluate_price_threshold(condition, stock)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Skipping invalid price alert %s for user %s on %s: %s",
                alert_id,
                user_id,
                symbol,
                exc,
            )
            continue
        if not matched:
            continue

        event = {
            "alert_id": alert_id,
            "alert_name": alert.get("name", alert_id),
            "symbols": [symbol],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "condition_type": "price_threshold",
            "user_id": user_id,
        }
        enqueue_job(
            JOB_DELIVER,
            {
                "user_id": user_id,
                "alert_id": alert_id,
                "event": event,
                "tick_id": payload.get("tick_id"),
            },
        )
        triggered += 1

    logger.info("evaluate_symbol %s: enqueued %s delivery job(s)", symbol, triggered)


def _process_deliver(job: Dict[str, Any]) -> bool:
    payload = job["payload"]
    user_id = payload["user_id"]
    alert_id = payload["alert_id"]
    event = dict(payload["event"])
    storage = UserAlertStorage(user_id)

    # A worker can die after the notification and trigger marker commit but before
    # completing the queue job. Stale-job recovery must not resend that event.
    if job["attempts"] > 1:
        event_at = _event_timestamp(event)
        last_triggered = storage.get_last_triggered(alert_id)
        if event_at is not None and last_triggered is not None:
            last_triggered = _as_utc(last_triggered)
            if last_triggered >= event_at:
                logger.info(
                    "Skipping already-delivered retry for alert %s (job %s, attempt %s)",
                    alert_id,
                    job["id"],
                    job["attempts"],
                )
                return False

    from src.storage.alert_watches import get_watch

    watch = get_watch(user_id, alert_id)
    if not watch:
        raise RuntimeError(f"Watch {alert_id!r} not found for user {user_id}")

    alert = watch["alert"]
    defaults = watch["defaults"]
    engine = AlertEngine([alert], storage=storage, defaults=defaults)

    if not engine.deliver_event(alert, event):
        raise RuntimeError(f"Delivery failed for alert {alert_id!r}")
    return True


def process_job_queue(
    worker_id: str | None = None,
    *,
    limit: int = 50,
    max_batches: int = 100,
) -> Dict[str, int]:
    init_database()
    wid = worker_id or new_worker_id()
    stats = {"evaluated": 0, "delivered": 0, "failed": 0}

    for batch in range(max_batches):
        eval_jobs = claim_jobs([JOB_EVALUATE_SYMBOL], wid, limit=limit)
        for job in eval_jobs:
            try:
                _process_evaluate_symbol(job)
                complete_job(job["id"])
                stats["evaluated"] += 1
            except Exception as exc:
                logger.exception("evaluate_symbol job %s failed", job["id"])
                fail_job(job["id"], str(exc))
                stats["failed"] += 1

        deliver_jobs = claim_jobs([JOB_DELIVER], wid, limit=limit)
        for job in deliver_jobs:
            try:
                delivered = _process_deliver(job)
                complete_job(job["id"])
                if delivered:
                    stats["delivered"] += 1
            except Exception as exc:
                logger.exception("deliver job %s failed", job["id"])
                fail_job(job["id"], str(exc))
                stats["failed"] += 1

        if not eval_jobs and not deliver_jobs:
            break
    else:
        logger.warning("Stopped processing alert jobs after %s batches", max_batches)

    return stats
