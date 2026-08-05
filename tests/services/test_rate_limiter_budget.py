"""Deterministic coverage for RateLimiter rolling budget and token refill."""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from src.services.api_client import RateLimiter


class _Clock:
    """Monotonic fake clock that advances when sleep() is called."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_rolling_budget_sleeps_when_window_is_full() -> None:
    """When call_times hits budget_max_calls, wait_if_needed sleeps out the oldest."""
    clock = _Clock()
    limiter = RateLimiter(calls_per_minute=60)
    # Prefer budget path: keep tokens available so only the rolling window blocks.
    limiter.tokens = 10.0
    limiter.last_refill = clock.now
    oldest = clock.now - 10.0
    limiter.call_times = deque(
        [oldest] + [clock.now - 1.0] * (limiter.budget_max_calls - 1)
    )

    with patch("src.services.api_client.time.time", clock.time):
        with patch("src.services.api_client.time.sleep", clock.sleep):
            limiter.wait_if_needed()

    assert clock.sleeps, "expected a budget sleep when the rolling window is full"
    assert abs(clock.sleeps[0] - 50.0) < 1e-6  # 60s window - 10s age
    # Exact window age must purge the oldest so we never exceed budget_max_calls.
    assert len(limiter.call_times) <= limiter.budget_max_calls
    assert oldest not in limiter.call_times
    assert limiter.call_times[-1] == clock.now
    # Sleep refills the bucket; still consumed exactly one token for this call.
    assert limiter.tokens == limiter.calls_per_minute - 1.0


def test_token_bucket_sleeps_when_tokens_exhausted() -> None:
    """Zero tokens forces a refill sleep before the call is recorded."""
    clock = _Clock()
    limiter = RateLimiter(calls_per_minute=60)
    limiter.tokens = 0.0
    limiter.last_refill = clock.now
    limiter.call_times.clear()

    with patch("src.services.api_client.time.time", clock.time):
        with patch("src.services.api_client.time.sleep", clock.sleep):
            limiter.wait_if_needed()

    assert clock.sleeps, "expected a token-refill sleep"
    assert clock.sleeps[0] > 0
    assert len(limiter.call_times) == 1
    assert limiter.tokens >= 0.0


def test_concurrent_wait_if_needed_keeps_call_times_consistent() -> None:
    """Parallel callers under the lock must not drop or duplicate call_times entries."""
    limiter = RateLimiter(calls_per_minute=1_000)
    limiter.tokens = float(limiter.calls_per_minute)
    limiter.call_times.clear()

    with patch("src.services.api_client.time.sleep", return_value=None):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: limiter.wait_if_needed(), range(40)))

    assert len(limiter.call_times) == 40
    assert limiter.tokens >= 0.0
