"""Tests for dashboard refresh process orchestration."""

import asyncio
import subprocess
from unittest.mock import MagicMock

from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from dashboard.backend.api import refresh


class FakeProcess:
    """Minimal subprocess stand-in for refresh lifecycle tests."""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.wait_timeouts: list[int] = []
        self.terminated = False
        self.killed = False

    def poll(self) -> int:
        return self.returncode

    def wait(self, timeout: int) -> int:
        self.wait_timeouts.append(timeout)
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def reset_refresh_state() -> None:
    refresh.refresh_status.update(
        {
            "is_running": False,
            "last_refresh": None,
            "last_status": "idle",
            "progress": "Idle.",
        }
    )
    refresh._refresh_process = None
    refresh._refresh_cancel_event.clear()


def test_run_daily_tracker_discards_child_output_to_prevent_deadlock(monkeypatch) -> None:
    reset_refresh_state()
    fake_process = FakeProcess(returncode=0)
    popen = MagicMock(return_value=fake_process)

    monkeypatch.setattr(refresh.subprocess, "Popen", popen)
    monkeypatch.setenv("REFRESH_TOP_N", "0")
    monkeypatch.setattr("src.alerts.alert_worker.run_check_once", lambda: {"triggered": 0})

    refresh.run_daily_tracker()

    _, kwargs = popen.call_args
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["stdout"] != subprocess.PIPE
    assert kwargs["stderr"] != subprocess.PIPE
    assert fake_process.wait_timeouts == [30]
    assert refresh.refresh_status["last_status"] == "success"
    assert refresh.refresh_status["is_running"] is False


def test_trigger_refresh_marks_running_before_worker_thread_starts(monkeypatch) -> None:
    reset_refresh_state()
    created_threads = []

    class FakeThread:
        def __init__(self, *, target, daemon: bool) -> None:
            self.target = target
            self.daemon = daemon
            self.started = False
            created_threads.append(self)

        def start(self) -> None:
            self.started = True

    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(refresh.threading, "Thread", FakeThread)

    response = asyncio.run(refresh.trigger_refresh(BackgroundTasks()))

    assert response.status == "started"
    assert response.is_running is True
    assert refresh.refresh_status["last_status"] == "running"
    assert refresh.refresh_status["progress"] == "Starting market-helm..."
    assert refresh.refresh_status["is_running"] is True
    assert len(created_threads) == 1
    assert created_threads[0].daemon is True
    assert created_threads[0].started is True


def test_refresh_mutations_require_auth_in_database_mode(tmp_path, monkeypatch) -> None:
    reset_refresh_state()
    db_path = tmp_path / "refresh-auth.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")

    from dashboard.backend.main import app
    from src.storage.database import init_database

    init_database()
    client = TestClient(app)

    assert client.post("/api/refresh").status_code == 401
    assert client.post("/api/refresh/cancel").status_code == 401
