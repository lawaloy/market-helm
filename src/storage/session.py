"""Signed session tokens for multi-user auth (stdlib only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


class AuthError(ValueError):
    pass


def _auth_secret() -> bytes:
    secret = (os.environ.get("MARKET_HELM_AUTH_SECRET") or "").strip()
    if len(secret) < 16:
        raise AuthError(
            "MARKET_HELM_AUTH_SECRET must be set (min 16 characters) when multi-user mode is enabled."
        )
    return secret.encode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def create_access_token(user_id: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + ttl_seconds,
    }
    body_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_auth_secret(), body_segment.encode("ascii"), hashlib.sha256).digest()
    return f"{body_segment}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        body_segment, sig_segment = token.split(".", 1)
        expected_sig = hmac.new(
            _auth_secret(),
            body_segment.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_decode(sig_segment), expected_sig):
            raise AuthError("Invalid token signature.")
        payload = json.loads(_b64url_decode(body_segment))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise AuthError("Token expired.")
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Invalid token subject.")
        return {"user_id": str(user_id)}
    except AuthError:
        raise
    except (ValueError, json.JSONDecodeError, KeyError) as exc:
        raise AuthError("Invalid access token.") from exc
