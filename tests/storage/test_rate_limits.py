"""Database-backed API rate-limit counter tests."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.storage.database import get_connection, init_database
from src.storage.rate_limits import consume_rate_limit


@pytest.fixture()
def rate_limit_database(tmp_path, monkeypatch) -> None:
    path = tmp_path / "rate-limits.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    init_database()


def test_consume_rate_limit_increments_and_resets(rate_limit_database) -> None:
    first = consume_rate_limit("login:key", now=121, window_seconds=60)
    second = consume_rate_limit("login:key", now=122, window_seconds=60)
    next_window = consume_rate_limit("login:key", now=180, window_seconds=60)

    assert (first.count, first.reset_at) == (1, 180)
    assert (second.count, second.reset_at) == (2, 180)
    assert (next_window.count, next_window.reset_at) == (1, 240)


def test_expired_rate_limit_rows_are_removed(rate_limit_database) -> None:
    consume_rate_limit("old:key", now=60, window_seconds=60)
    consume_rate_limit("new:key", now=120, window_seconds=60)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT bucket_key FROM api_rate_limits ORDER BY bucket_key"
        ).fetchall()
    assert [row["bucket_key"] for row in rows] == ["new:key"]


def test_consume_rate_limit_serializes_concurrent_increments(
    rate_limit_database,
) -> None:
    """Overlapping upserts must not lose counts (BEGIN IMMEDIATE writer mutex)."""
    workers = 8
    barrier = threading.Barrier(workers)
    counts: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait(timeout=5)
        usage = consume_rate_limit("login:key", now=121, window_seconds=60)
        with lock:
            counts.append(usage.count)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        for future in futures:
            future.result(timeout=10)

    assert sorted(counts) == list(range(1, workers + 1))
