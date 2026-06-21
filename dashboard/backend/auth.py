"""Shared auth helpers for dashboard API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from src.storage.database import database_enabled
from src.storage.session import AuthError, decode_access_token


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


async def optional_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not database_enabled():
        return None
    return bearer_user_id(authorization)


async def require_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not database_enabled():
        return None
    user_id = bearer_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user_id
