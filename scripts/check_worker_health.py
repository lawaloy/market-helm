#!/usr/bin/env python3
"""Probe ``/health/worker`` for staging readiness and recovery drills."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def _fetch(url: str, timeout: float) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}, got {type(payload).__name__}")
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8012/health/worker",
        help="Worker health endpoint URL",
    )
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--print-worker-id",
        action="store_true",
        help="Print worker_id and exit 0 when the probe is healthy",
    )
    parser.add_argument(
        "--previous-worker-id",
        default=os.environ.get("PREVIOUS_WORKER_ID") or None,
        help="Require a different worker_id (also reads PREVIOUS_WORKER_ID)",
    )
    args = parser.parse_args(argv)

    try:
        payload = _fetch(args.url, args.timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        print(f"worker health probe failed: {exc}", file=sys.stderr)
        return 1

    if payload.get("ok") is not True:
        print(f"worker health not ok: {payload!r}", file=sys.stderr)
        return 1

    worker_id = payload.get("worker_id") or ""
    if args.previous_worker_id is not None:
        if not worker_id or worker_id == args.previous_worker_id:
            print(
                "worker_id did not change after recovery: "
                f"previous={args.previous_worker_id!r} current={worker_id!r}",
                file=sys.stderr,
            )
            return 1

    if args.print_worker_id:
        if not worker_id:
            print("worker health missing worker_id", file=sys.stderr)
            return 1
        print(worker_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
