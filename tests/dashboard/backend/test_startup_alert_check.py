"""Startup alert check and lifespan DB init must soft-fail, not abort boot."""

import asyncio
from unittest.mock import MagicMock, patch

from dashboard.backend import main as backend_main


def test_startup_alert_check_swallows_worker_exception(caplog):
    """run_check_once raising must log a warning and not propagate."""
    with patch(
        "src.alerts.alert_worker.run_check_once",
        side_effect=RuntimeError("db unavailable"),
    ):
        with caplog.at_level("WARNING"):
            backend_main._startup_alert_check()

    assert any("Startup alert check failed" in r.message for r in caplog.records)


def test_startup_alert_check_logs_triggered_count(caplog):
    """Successful startup check with triggers should log an info line."""
    with patch(
        "src.alerts.alert_worker.run_check_once",
        return_value={"triggered": 2},
    ):
        with caplog.at_level("INFO"):
            backend_main._startup_alert_check()

    assert any("triggered 2 watch" in r.message for r in caplog.records)


def test_lifespan_continues_when_db_init_fails(caplog):
    """DB init failure must not prevent lifespan from yielding (app still boots)."""
    fake_thread = MagicMock()

    with patch(
        "src.storage.database.init_database",
        side_effect=RuntimeError("cannot open db"),
    ), patch(
        "threading.Thread",
        return_value=fake_thread,
    ) as thread_ctor:
        with caplog.at_level("WARNING"):

            async def _run():
                async with backend_main.lifespan(MagicMock()):
                    pass

            asyncio.run(_run())

    assert any("Database init skipped" in r.message for r in caplog.records)
    thread_ctor.assert_called_once()
    kwargs = thread_ctor.call_args.kwargs
    assert kwargs.get("target") is backend_main._startup_alert_check
    assert kwargs.get("daemon") is True
    fake_thread.start.assert_called_once()
