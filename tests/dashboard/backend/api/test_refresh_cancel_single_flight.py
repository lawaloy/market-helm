"""Cancel must not clear is_running before the worker finishes teardown."""

import asyncio
from unittest.mock import MagicMock

from fastapi import BackgroundTasks

from dashboard.backend.api import refresh
from tests.dashboard.backend.api.test_refresh import FakeProcess, reset_refresh_state


def test_cancel_leaves_running_flag_for_worker_finally() -> None:
    """Clearing is_running in cancel previously allowed a second Finnhub child."""
    reset_refresh_state()
    fake_process = FakeProcess(returncode=-15, running=True)
    refresh.refresh_status["is_running"] = True
    refresh.refresh_status["last_status"] = "running"
    refresh._refresh_process = fake_process

    response = asyncio.run(refresh.cancel_refresh())

    assert refresh._refresh_cancel_event.is_set()
    assert fake_process.terminated is True
    assert response.last_status == "cancelled"
    # Worker still owns the single-flight flag until its finally block.
    assert response.is_running is True
    assert refresh.refresh_status["is_running"] is True


def test_retrigger_blocked_while_cancelled_worker_still_tearing_down(monkeypatch) -> None:
    reset_refresh_state()
    fake_process = FakeProcess(returncode=-15, running=True)
    refresh.refresh_status["is_running"] = True
    refresh.refresh_status["last_status"] = "running"
    refresh._refresh_process = fake_process

    asyncio.run(refresh.cancel_refresh())

    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    created_threads: list = []

    class FakeThread:
        def __init__(self, *, target, daemon: bool) -> None:
            self.target = target
            self.daemon = daemon
            created_threads.append(self)

        def start(self) -> None:
            raise AssertionError("must not start a second refresh during teardown")

    monkeypatch.setattr(refresh.threading, "Thread", FakeThread)

    response = asyncio.run(refresh.trigger_refresh(BackgroundTasks()))

    assert response.status == "already_running"
    assert response.is_running is True
    assert created_threads == []


def test_worker_finally_releases_single_flight_after_cancel(monkeypatch) -> None:
    """After cancel signals, the worker finally must clear is_running for a clean re-trigger."""
    reset_refresh_state()
    fake_process = FakeProcess(returncode=-15, running=True)
    alert_check = MagicMock(return_value={"triggered": 0})

    def popen_and_cancel(*_args, **_kwargs):
        refresh._refresh_cancel_event.set()
        return fake_process

    monkeypatch.setattr(
        refresh.subprocess, "Popen", MagicMock(side_effect=popen_and_cancel)
    )
    monkeypatch.setenv("REFRESH_TOP_N", "0")
    monkeypatch.setattr("src.alerts.alert_worker.run_check_once", alert_check)
    monkeypatch.setattr(refresh.time, "sleep", lambda _seconds: None)

    refresh.refresh_status["is_running"] = True
    refresh.run_daily_tracker()

    assert refresh.refresh_status["last_status"] == "cancelled"
    assert refresh.refresh_status["is_running"] is False
    assert refresh._refresh_process is None
    alert_check.assert_not_called()
