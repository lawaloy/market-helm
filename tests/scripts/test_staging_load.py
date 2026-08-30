"""Tests for the bounded staging capacity baseline."""

from __future__ import annotations

import pytest

from scripts.staging_acceptance import AcceptanceError
from scripts.staging_load import Sample, percentile, run_baseline


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([40, 10, 30, 20], 0.50) == 20
    assert percentile([40, 10, 30, 20], 0.95) == 40
    assert percentile([], 0.95) == 0


def test_baseline_passes_and_contains_no_request_details() -> None:
    seen = []

    def requester(url: str, timeout: float) -> Sample:
        seen.append((url, timeout))
        return Sample(200, float(len(seen)))

    report = run_baseline(
        "http://127.0.0.1:8012",
        requests=10,
        concurrency=2,
        timeout=3,
        max_error_rate=0,
        max_p95_ms=20,
        requester=requester,
    )

    assert report["status"] == "passed"
    assert report["result"]["status_counts"] == {"200": 10}
    assert seen == [("http://127.0.0.1:8012/health/ready", 3)] * 10
    assert "samples" not in report


def test_baseline_fails_thresholds() -> None:
    samples = iter([Sample(200, 100), Sample(503, 200, "HTTP 503")])
    report = run_baseline(
        "https://staging.example.com",
        requests=2,
        concurrency=1,
        timeout=1,
        max_error_rate=0,
        max_p95_ms=150,
        requester=lambda _url, _timeout: next(samples),
    )
    assert report["status"] == "failed"
    assert report["result"]["failures"] == 1
    assert report["result"]["p95_ms"] == 200


@pytest.mark.parametrize(
    ("requests", "concurrency", "timeout", "error_rate", "p95"),
    [(0, 1, 1, 0, 1), (1, 2, 1, 0, 1), (1, 1, 0, 0, 1), (1, 1, 1, 1.1, 1)],
)
def test_baseline_rejects_invalid_limits(
    requests, concurrency, timeout, error_rate, p95
) -> None:
    with pytest.raises(AcceptanceError):
        run_baseline(
            "https://staging.example.com",
            requests=requests,
            concurrency=concurrency,
            timeout=timeout,
            max_error_rate=error_rate,
            max_p95_ms=p95,
        )


def test_baseline_rejects_mutating_or_unknown_endpoint() -> None:
    with pytest.raises(AcceptanceError, match="read-only"):
        run_baseline(
            "https://staging.example.com",
            endpoint="/api/refresh",
            requests=1,
            concurrency=1,
            timeout=1,
            max_error_rate=0,
            max_p95_ms=100,
        )
