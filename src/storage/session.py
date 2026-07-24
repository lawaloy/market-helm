"""Signed session tokens for multi-user auth (stdlib only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
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
        if not isinstance(payload, dict):
            raise AuthError("Invalid access token.")
        # Treat exp == now as expired so zero-TTL tokens cannot authenticate.
        # Non-finite exp (Infinity from allow_nan JSON) must not OverflowError → 500.
        exp = payload.get("exp", 0)
        if isinstance(exp, bool) or not isinstance(exp, (int, float)):
            raise AuthError("Invalid access token.")
        if not math.isfinite(exp):
            raise AuthError("Invalid access token.")
        if int(exp) <= int(time.time()):
            raise AuthError("Token expired.")
        user_id = payload.get("sub")
        # Reject non-strings (True/123/{} stringify into fake IDs) and blank subjects.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AuthError("Invalid token subject.")
        return {"user_id": user_id.strip()}
    except AuthError:
        raise
    except (ValueError, json.JSONDecodeError, KeyError, OverflowError, TypeError) as exc:
        raise AuthError("Invalid access token.") from exc
