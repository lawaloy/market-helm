"""Concurrent POST /refresh must start only one Finnhub-burning child."""

import asyncio
import threading

from fastapi import BackgroundTasks

from dashboard.backend.api import refresh
from tests.dashboard.backend.api.test_refresh import reset_refresh_state


def test_concurrent_trigger_refresh_starts_only_one_thread(monkeypatch) -> None:
    """Check-then-set without a lock previously allowed overlapping starts."""
    reset_refresh_state()
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")

    created_threads: list = []
    real_thread = threading.Thread

    class FakeRefreshThread:
        def __init__(self, *, target, daemon: bool) -> None:
            self.target = target
            self.daemon = daemon
            created_threads.append(self)

        def start(self) -> None:
            # Do not run the tracker; we only care that one worker is spawned.
            pass

    monkeypatch.setattr(refresh.threading, "Thread", FakeRefreshThread)

    results: list = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait(timeout=5)
        results.append(asyncio.run(refresh.trigger_refresh(BackgroundTasks())))

    # Use the real Thread class for test harness workers (module Thread is patched).
    workers = [real_thread(target=worker) for _ in range(8)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join(timeout=10)

    assert len(results) == 8
    started = [r for r in results if r.status == "started"]
    already = [r for r in results if r.status == "already_running"]
    assert len(started) == 1
    assert len(already) == 7
    assert len(created_threads) == 1
    assert refresh.refresh_status["is_running"] is True
