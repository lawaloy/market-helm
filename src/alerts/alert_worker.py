"""Scheduled alert evaluation worker (cron, Task Scheduler, systemd, or long-running process)."""

from __future__ import annotations

import logging
import os
import signal
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300
MIN_INTERVAL_SECONDS = 60


def resolve_interval_seconds(explicit: Optional[int] = None) -> int:
    """Seconds between checks when running in loop mode."""
    if explicit is not None:
        return max(MIN_INTERVAL_SECONDS, explicit)
    raw = os.environ.get("ALERT_CHECK_INTERVAL_SECONDS", "").strip()
    if raw:
        try:
            return max(MIN_INTERVAL_SECONDS, int(raw))
        except ValueError:
            logger.warning(
                "Invalid ALERT_CHECK_INTERVAL_SECONDS=%r; using default %ss",
                raw,
                DEFAULT_INTERVAL_SECONDS,
            )
    return DEFAULT_INTERVAL_SECONDS


def run_check_once() -> Dict[str, Any]:
    from src.alerts.alert_runner import evaluate_alerts_from_latest_data

    return evaluate_alerts_from_latest_data()


def log_check_result(result: Dict[str, Any]) -> None:
    triggered = int(result.get("triggered") or 0)
    last_date = result.get("last_data_date")
    message = result.get("message")
    if triggered:
        logger.info("Alert check triggered %s watch(es) (data %s)", triggered, last_date)
        for event in result.get("events") or []:
            logger.info(
                "  - %s symbols=%s",
                event.get("alert_name", event.get("alert_id")),
                event.get("symbols"),
            )
    elif message:
        logger.info("Alert check: %s (data %s)", message, last_date)
    else:
        logger.info("Alert check complete: no triggers (data %s)", last_date)


def run_worker_once() -> Dict[str, Any]:
    result = run_check_once()
    log_check_result(result)
    return result


def run_worker_loop(
    interval_seconds: Optional[int] = None,
    *,
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """Evaluate watches on a fixed interval until SIGINT/SIGTERM."""
    interval = resolve_interval_seconds(interval_seconds)
    stop = False

    def _request_stop(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    logger.info("Alert worker started (interval %ss); Ctrl+C to stop", interval)
    while not stop:
        run_worker_once()
        if stop:
            break
        deadline = time.monotonic() + interval
        while time.monotonic() < deadline:
            if stop or (should_stop and should_stop()):
                stop = True
                break
            time.sleep(1)
    logger.info("Alert worker stopped")
