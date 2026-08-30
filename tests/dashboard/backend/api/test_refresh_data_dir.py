"""Fetch New must pass DATA_DIR through to the tracker child process."""

from typing import Optional
from unittest.mock import MagicMock

from dashboard.backend.api import refresh


class _FakeProcess:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    def poll(self) -> Optional[int]:
        return self.returncode

    def wait(self, timeout: int) -> int:
        return self.returncode

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None


def _reset() -> None:
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


def test_run_daily_tracker_forwards_data_dir_to_child(monkeypatch) -> None:
    """A rebuilt env dict that drops DATA_DIR would send Fetch New writes to ./data."""
    _reset()
    popen = MagicMock(return_value=_FakeProcess(returncode=0))
    monkeypatch.setattr(refresh.subprocess, "Popen", popen)
    monkeypatch.setenv("DATA_DIR", "/var/lib/markethelm/data")
    monkeypatch.setenv("REFRESH_TOP_N", "0")
    monkeypatch.setattr("src.alerts.alert_worker.run_check_once", lambda: {"triggered": 0})

    refresh.run_daily_tracker()

    child_env = popen.call_args.kwargs["env"]
    assert child_env["DATA_DIR"] == "/var/lib/markethelm/data"
    assert refresh.refresh_status["last_status"] == "success"
