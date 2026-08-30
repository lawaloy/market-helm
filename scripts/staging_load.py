#!/usr/bin/env python3
"""Run a bounded, read-only capacity baseline against MarketHelm staging."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.staging_acceptance import AcceptanceError, normalize_base_url


@dataclass(frozen=True)
class Sample:
    status: int
    duration_ms: float
    error: str | None = None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(url: str, timeout: float) -> Sample:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "markethelm-staging-load/1"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            response.read()
            status = response.status
            error = None
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
        error = f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        status = 0
        error = type(exc).__name__
    return Sample(status, (time.perf_counter() - started) * 1000, error)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def run_baseline(
    base_url: str,
    *,
    endpoint: str = "/health/ready",
    requests: int,
    concurrency: int,
    timeout: float,
    max_error_rate: float,
    max_p95_ms: float,
    requester: Callable[[str, float], Sample] = _request,
) -> dict:
    if requests < 1 or concurrency < 1 or concurrency > requests:
        raise AcceptanceError(
            "Requests and concurrency must be positive; concurrency cannot exceed requests."
        )
    if timeout <= 0 or max_p95_ms <= 0 or not 0 <= max_error_rate <= 1:
        raise AcceptanceError("Timeout/P95 must be positive and error rate must be between 0 and 1.")
    if endpoint not in {"/health/live", "/health/ready", "/health/worker", "/metrics"}:
        raise AcceptanceError(
            "Endpoint must be a read-only MarketHelm health or metrics endpoint."
        )
    safe_base = normalize_base_url(base_url)
    url = f"{safe_base}{endpoint}"
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(requester, url, timeout) for _ in range(requests)]
        samples = [future.result() for future in as_completed(futures)]
    elapsed = time.perf_counter() - started
    failures = sum(sample.status != 200 for sample in samples)
    durations = [sample.duration_ms for sample in samples]
    error_rate = failures / requests
    p95_ms = percentile(durations, 0.95)
    passed = error_rate <= max_error_rate and p95_ms <= max_p95_ms
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": safe_base,
        "endpoint": endpoint,
        "status": "passed" if passed else "failed",
        "configuration": {
            "requests": requests,
            "concurrency": concurrency,
            "timeout_seconds": timeout,
            "max_error_rate": max_error_rate,
            "max_p95_ms": max_p95_ms,
        },
        "result": {
            "completed": len(samples),
            "failures": failures,
            "error_rate": round(error_rate, 6),
            "p50_ms": round(percentile(durations, 0.50), 3),
            "p95_ms": round(p95_ms, 3),
            "p99_ms": round(percentile(durations, 0.99), 3),
            "throughput_per_second": round(requests / elapsed, 3) if elapsed else 0.0,
            "status_counts": {
                str(status): sum(sample.status == status for sample in samples)
                for status in sorted({sample.status for sample in samples})
            },
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--endpoint",
        choices=("/health/live", "/health/ready", "/health/worker", "/metrics"),
        default="/health/ready",
    )
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_baseline(
            args.base_url,
            endpoint=args.endpoint,
            requests=args.requests,
            concurrency=args.concurrency,
            timeout=args.timeout,
            max_error_rate=args.max_error_rate,
            max_p95_ms=args.max_p95_ms,
        )
    except AcceptanceError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {args.report}")
    result = report["result"]
    print(
        f"{report['status'].upper()}: {result['completed']} requests, "
        f"{result['failures']} failures, p95={result['p95_ms']}ms, "
        f"throughput={result['throughput_per_second']}/s"
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
