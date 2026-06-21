"""User accounts (email + password) for multi-user mode."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .database import get_connection

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class UserError(ValueError):
    pass


def _hash_password(password: str) -> str:
    if len(password) < 8:
        raise UserError("Password must be at least 8 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n_raw, r_raw, p_raw, salt_hex, digest_hex = stored.split("$", 5)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
            dklen=len(expected),
        )
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_user(email: str, password: str) -> Dict[str, Any]:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise UserError("A valid email address is required.")

    user_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    password_hash = _hash_password(password)

    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, normalized, password_hash, created_at),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise UserError("An account with this email already exists.") from exc
            raise

    return {"id": user_id, "email": normalized, "created_at": created_at}


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    normalized = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}
