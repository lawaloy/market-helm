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
# Bound plaintext length so register/login cannot feed multi-MB strings into scrypt.
MAX_PASSWORD_LENGTH = 128
# RFC 5321 practical maximum; also reject control chars / junk local@domain shapes.
MAX_EMAIL_LENGTH = 254


class UserError(ValueError):
    pass


def _normalize_email(email: str) -> str:
    """Strip/lower-case and fail closed on length, control chars, or junk shapes."""
    if not isinstance(email, str):
        raise UserError("A valid email address is required.")
    # Reject oversized input before strip so multi-MB payloads never hit the DB path.
    if len(email) > MAX_EMAIL_LENGTH:
        raise UserError(
            f"Email must be at most {MAX_EMAIL_LENGTH} characters."
        )
    normalized = email.strip().lower()
    if not normalized or len(normalized) > MAX_EMAIL_LENGTH:
        raise UserError("A valid email address is required.")
    if any(ch in normalized for ch in ("\n", "\r", "\0", " ", "\t", "\f", "\v")):
        raise UserError("A valid email address is required.")
    if normalized.count("@") != 1:
        raise UserError("A valid email address is required.")
    local, domain = normalized.split("@", 1)
    if not local or not domain:
        raise UserError("A valid email address is required.")
    return normalized


def _hash_password(password: str) -> str:
    if len(password) < 8:
        raise UserError("Password must be at least 8 characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise UserError(
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
        )
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
    # Reject oversized plaintext before scrypt so login cannot be CPU-DoS'd.
    if len(password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        scheme, n_raw, r_raw, p_raw, salt_hex, digest_hex = stored.split("$", 5)
        if scheme != "scrypt":
            return False
        n = int(n_raw)
        r = int(r_raw)
        p = int(p_raw)
        # Only accept the cost parameters we mint. A poisoned password_hash with
        # huge N/r/p would otherwise turn /api/auth/login into a CPU DoS.
        if n != _SCRYPT_N or r != _SCRYPT_R or p != _SCRYPT_P:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_user(email: str, password: str) -> Dict[str, Any]:
    normalized = _normalize_email(email)

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
    try:
        normalized = _normalize_email(email)
    except UserError:
        return None
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
            "SELECT id, email, created_at, email_verified_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"],
            "email_verified": bool(row["email_verified_at"])}


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    try:
        normalized = _normalize_email(email)
    except UserError:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, created_at, email_verified_at FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"],
            "email_verified": bool(row["email_verified_at"])}


def update_password(user_id: str, password: str) -> None:
    password_hash = _hash_password(password)
    with get_connection() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def mark_email_verified(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET email_verified_at = ? WHERE id = ? AND email_verified_at IS NULL",
            (datetime.now(timezone.utc).isoformat(), user_id),
        )
