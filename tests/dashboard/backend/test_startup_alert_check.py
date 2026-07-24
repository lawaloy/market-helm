"""Startup lifespan must soft-fail DB init and alert checks without aborting boot."""

import asyncio
import logging
from unittest.mock import MagicMock, patch

from dashboard.backend.main import _startup_alert_check, app, lifespan


def test_startup_alert_check_swallows_worker_errors(caplog):
    with patch(
        "src.alerts.alert_worker.run_check_once",
        side_effect=RuntimeError("worker down"),
    ):
        with caplog.at_level(logging.WARNING):
            _startup_alert_check()

    assert "Startup alert check failed" in caplog.text
    assert "worker down" in caplog.text


def test_startup_alert_check_logs_triggered_count(caplog):
    with patch(
        "src.alerts.alert_worker.run_check_once",
        return_value={"triggered": 3},
    ):
        with caplog.at_level(logging.INFO):
            _startup_alert_check()

    assert "triggered 3 watch(es)" in caplog.text


def test_lifespan_swallows_database_init_errors(caplog):
    """Broken DB init must not prevent the API from serving requests."""
    thread = MagicMock()

    async def _run():
        with patch(
            "src.storage.database.init_database",
            side_effect=RuntimeError("db unavailable"),
        ):
            with patch("dashboard.backend.main.threading.Thread", return_value=thread):
                with caplog.at_level(logging.WARNING):
                    async with lifespan(app):
                        pass

    asyncio.run(_run())

    assert "Database init skipped" in caplog.text
    assert "db unavailable" in caplog.text
    thread.start.assert_called_once()
