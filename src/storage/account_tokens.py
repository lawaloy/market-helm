"""Single-use, hashed account lifecycle tokens."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from .database import get_connection

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"
TOKEN_TTL_MINUTES = 60


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(user_id: str, purpose: str, *, ttl_minutes: int = TOKEN_TTL_MINUTES) -> str:
    if purpose not in {VERIFY_EMAIL, RESET_PASSWORD}:
        raise ValueError("Unsupported account token purpose")
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=max(1, min(ttl_minutes, 1440)))
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM account_tokens WHERE user_id = ? AND purpose = ?",
            (user_id, purpose),
        )
        conn.execute(
            """INSERT INTO account_tokens
               (token_hash, user_id, purpose, expires_at, consumed_at, created_at)
               VALUES (?, ?, ?, ?, NULL, ?)""",
            (_digest(token), user_id, purpose, expires.isoformat(), now.isoformat()),
        )
    return token


def consume_token(token: str, purpose: str) -> Optional[str]:
    if not isinstance(token, str) or not token or len(token) > 256:
        return None
    now = datetime.now(timezone.utc).isoformat()
    token_hash = _digest(token)
    with get_connection() as conn:
        row = conn.execute(
            """SELECT user_id FROM account_tokens
               WHERE token_hash = ? AND purpose = ? AND consumed_at IS NULL
                 AND expires_at > ?""",
            (token_hash, purpose, now),
        ).fetchone()
        if not row:
            return None
        updated = conn.execute(
            """UPDATE account_tokens SET consumed_at = ?
               WHERE token_hash = ? AND consumed_at IS NULL""",
            (now, token_hash),
        )
        if updated.rowcount != 1:
            return None
        return str(row["user_id"])


def revoke_tokens(user_id: str, purpose: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM account_tokens WHERE user_id = ? AND purpose = ?",
            (user_id, purpose),
        )
