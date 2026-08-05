"""Shared auth helpers for dashboard API routes."""

from __future__ import annotations

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
    if get_user_by_id(user_id) is None:
        return None
    return user_id


async def optional_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not database_enabled():
        return None
    return _existing_user_id(bearer_user_id(authorization))


async def require_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not database_enabled():
        return None
    user_id = bearer_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    # Match /api/auth/me: a still-valid signature for a deleted user must not
    # authorize protected alert/refresh routes (empty 200 or FK 500).
    if get_user_by_id(user_id) is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return user_id
