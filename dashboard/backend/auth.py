"""Shared auth helpers for dashboard API routes."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException

from src.storage.database import database_enabled
from src.storage.session import AuthError, decode_access_token
from src.storage.users import get_user_by_id


def bearer_user_id(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return decode_access_token(token)["user_id"]
    except AuthError:
        return None


def _existing_user_id(user_id: Optional[str]) -> Optional[str]:
    """Return *user_id* only when the account still exists (deleted → None)."""
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if user is None:
        return None
    if _verification_required() and not user.get("email_verified"):
        return None
    return user_id


def bearer_session(authorization: Optional[str]) -> Optional[dict]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return decode_access_token(token)
    except AuthError:
        return None


def _verification_required() -> bool:
    return (os.environ.get("MARKET_HELM_REQUIRE_EMAIL_VERIFICATION") or "").lower() in {
        "1", "true", "yes", "on"
    }


async def optional_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not database_enabled():
        return None
    session = bearer_session(authorization)
    if not session:
        return None
    user = get_user_by_id(session["user_id"])
    if not user or user["session_version"] != session["session_version"]:
        return None
    return _existing_user_id(session["user_id"])


async def require_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not database_enabled():
        return None
    session = bearer_session(authorization)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    user_id = session["user_id"]
    # Match /api/auth/me: a still-valid signature for a deleted user must not
    # authorize protected alert/refresh routes (empty 200 or FK 500).
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    if user["session_version"] != session["session_version"]:
        raise HTTPException(status_code=401, detail="Session revoked.")
    if _verification_required() and not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="Email verification required.")
    return user_id
