"""Extreme REFRESH_* env values must clamp to safe Finnhub/CPU ceilings."""

from typing import Optional
from unittest.mock import MagicMock

from dashboard.backend.api import refresh


class _FakeProcess:
    def __init__(self, returncode: int = 0, *, running: bool = False) -> None:
        self.returncode = returncode
        self.terminated = False
        self._running = running

    def poll(self) -> Optional[int]:
        if self._running:
            return None
        return self.returncode

    def wait(self, timeout: int) -> int:
        self._running = False
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self._running = False

    def kill(self) -> None:
        self._running = False


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


def test_resolve_refresh_top_n_clamps_extreme_values(monkeypatch) -> None:
    monkeypatch.setenv("REFRESH_TOP_N", "100000000")
    assert refresh._resolve_refresh_top_n() == refresh.MAX_REFRESH_TOP_N

    monkeypatch.setenv("REFRESH_TOP_N", str(refresh.MAX_REFRESH_TOP_N))
    assert refresh._resolve_refresh_top_n() == refresh.MAX_REFRESH_TOP_N

    monkeypatch.setenv("REFRESH_TOP_N", "25")
    assert refresh._resolve_refresh_top_n() == 25

    monkeypatch.setenv("REFRESH_TOP_N", "0")
    assert refresh._resolve_refresh_top_n() == 0

    # Negatives must not collapse to unlimited (0) via max(0, n).
    monkeypatch.setenv("REFRESH_TOP_N", "-1")
    assert refresh._resolve_refresh_top_n() == refresh.DEFAULT_REFRESH_TOP_N

    monkeypatch.setenv("REFRESH_TOP_N", "-999")
    assert refresh._resolve_refresh_top_n() == refresh.DEFAULT_REFRESH_TOP_N


def test_resolve_refresh_timeout_clamps_extreme_values(monkeypatch) -> None:
    monkeypatch.setenv("REFRESH_TIMEOUT_SECONDS", "999999999")
    assert (
        refresh._resolve_refresh_timeout_seconds()
        == refresh.MAX_REFRESH_TIMEOUT_SECONDS
    )

    monkeypatch.setenv(
        "REFRESH_TIMEOUT_SECONDS", str(refresh.MAX_REFRESH_TIMEOUT_SECONDS)
    )
    assert (
        refresh._resolve_refresh_timeout_seconds()
        == refresh.MAX_REFRESH_TIMEOUT_SECONDS
    )

    monkeypatch.setenv("REFRESH_TIMEOUT_SECONDS", "120")
    assert refresh._resolve_refresh_timeout_seconds() == 120


def test_resolve_refresh_max_workers_clamps_band(monkeypatch) -> None:
    monkeypatch.setenv("REFRESH_MAX_WORKERS", "99")
    assert refresh._resolve_refresh_max_workers() == refresh.MAX_REFRESH_WORKERS

    monkeypatch.setenv("REFRESH_MAX_WORKERS", "0")
    assert refresh._resolve_refresh_max_workers() == 1

    monkeypatch.setenv("REFRESH_MAX_WORKERS", "not-an-int")
    assert refresh._resolve_refresh_max_workers() == refresh.DEFAULT_REFRESH_WORKERS


def test_run_daily_tracker_honors_top_n_and_timeout_ceilings(monkeypatch) -> None:
    """Poisoned env must not pass unbounded --top-n or wait forever for timeout."""
    _reset()
    fake_process = _FakeProcess(returncode=0, running=True)
    popen = MagicMock(return_value=fake_process)
    times = {"now": 0.0}

    monkeypatch.setattr(refresh.subprocess, "Popen", popen)
    monkeypatch.setenv("REFRESH_TOP_N", "100000000")
    monkeypatch.setenv("REFRESH_TIMEOUT_SECONDS", "999999999")
    monkeypatch.setenv("REFRESH_MAX_WORKERS", "64")
    monkeypatch.setattr(refresh.time, "time", lambda: times["now"])

    def advance_sleep(_seconds: float) -> None:
        # Jump past the clamped timeout on the first poll iteration.
        times["now"] = float(refresh.MAX_REFRESH_TIMEOUT_SECONDS + 1)

    monkeypatch.setattr(refresh.time, "sleep", advance_sleep)
    monkeypatch.setattr("src.alerts.alert_worker.run_check_once", lambda: {"triggered": 0})

    refresh.run_daily_tracker()

    command = popen.call_args.args[0]
    assert command[command.index("--top-n") + 1] == str(refresh.MAX_REFRESH_TOP_N)
    assert popen.call_args.kwargs["env"]["STOCK_FETCH_MAX_WORKERS"] == str(
        refresh.MAX_REFRESH_WORKERS
    )
    assert refresh.refresh_status["last_status"] == "timeout"
    assert fake_process.terminated is True


def test_run_daily_tracker_negative_top_n_keeps_default_cap(monkeypatch) -> None:
    """Typo REFRESH_TOP_N=-1 must still pass --top-n DEFAULT, not unbounded."""
    _reset()
    fake_process = _FakeProcess(returncode=0, running=False)
    popen = MagicMock(return_value=fake_process)

    monkeypatch.setattr(refresh.subprocess, "Popen", popen)
    monkeypatch.setenv("REFRESH_TOP_N", "-1")
    monkeypatch.setenv("REFRESH_NO_SCREENER", "1")
    monkeypatch.setattr("src.alerts.alert_worker.run_check_once", lambda: {"triggered": 0})

    refresh.run_daily_tracker()

    command = popen.call_args.args[0]
    assert "--top-n" in command
    assert command[command.index("--top-n") + 1] == str(refresh.DEFAULT_REFRESH_TOP_N)
