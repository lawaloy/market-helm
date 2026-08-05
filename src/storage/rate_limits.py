"""Atomic, database-backed API rate-limit counters."""

from __future__ import annotations

from dataclasses import dataclass

from .database import get_connection


@dataclass(frozen=True)
class RateLimitUsage:
    count: int
    reset_at: int


def consume_rate_limit(
    bucket_key: str,
    *,
    now: int,
    window_seconds: int,
) -> RateLimitUsage:
    """Atomically increment one fixed-window counter."""
    window_start = now - (now % window_seconds)
    reset_at = window_start + window_seconds
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM api_rate_limits WHERE expires_at <= ?",
            (now,),
        )
        row = conn.execute(
            """INSERT INTO api_rate_limits (
                   bucket_key, window_start, request_count, expires_at
               ) VALUES (?, ?, 1, ?)
               ON CONFLICT(bucket_key, window_start) DO UPDATE SET
                   request_count = api_rate_limits.request_count + 1,
                   expires_at = excluded.expires_at
               RETURNING request_count""",
            (bucket_key, window_start, reset_at),
        ).fetchone()
    return RateLimitUsage(count=int(row["request_count"]), reset_at=reset_at)
