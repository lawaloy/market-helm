"""Malformed token payloads must raise AuthError, not AttributeError/OverflowError."""

import base64
import hashlib
import hmac
import json
import time

import pytest

from src.storage import session as session_mod
from src.storage.session import AuthError, decode_access_token


@pytest.fixture
def auth_secret(monkeypatch):
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")


def _sign_raw(body_bytes: bytes) -> str:
    body = base64.urlsafe_b64encode(body_bytes).decode().rstrip("=")
    sig = hmac.new(
        session_mod._auth_secret(),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def _sign_payload(payload) -> str:
    return _sign_raw(json.dumps(payload, allow_nan=True, separators=(",", ":")).encode())


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],
        "token",
        42,
        True,
        None,
    ],
)
def test_non_dict_payload_raises_auth_error(auth_secret, payload) -> None:
    token = _sign_raw(json.dumps(payload).encode())
    with pytest.raises(AuthError, match="Invalid access token"):
        decode_access_token(token)


@pytest.mark.parametrize("exp", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_exp_raises_auth_error(auth_secret, exp) -> None:
    token = _sign_payload({"sub": "user-1", "exp": exp})
    with pytest.raises(AuthError, match="Invalid access token"):
        decode_access_token(token)


def test_non_numeric_exp_raises_auth_error(auth_secret) -> None:
    token = _sign_payload({"sub": "user-1", "exp": "later"})
    with pytest.raises(AuthError, match="Invalid access token"):
        decode_access_token(token)


def test_bool_exp_rejected(auth_secret, monkeypatch) -> None:
    # bool is a subclass of int; must not authenticate via True/False.
    monkeypatch.setattr(time, "time", lambda: 1_000_000)
    token = _sign_payload({"sub": "user-1", "exp": True})
    with pytest.raises(AuthError, match="Invalid access token"):
        decode_access_token(token)


@pytest.mark.parametrize(
    "sub",
    [
        True,
        False,
        123,
        0,
        1.5,
        [],
        {},
        ["user-1"],
        {"id": "user-1"},
        "   ",
        "\t\n",
    ],
)
def test_non_string_or_blank_subject_raises_auth_error(auth_secret, monkeypatch, sub) -> None:
    """Truthy non-strings must not become str(sub) user ids; whitespace is blank."""
    monkeypatch.setattr(time, "time", lambda: 1_000_000)
    token = _sign_payload({"sub": sub, "exp": 1_000_100})
    with pytest.raises(AuthError, match="subject"):
        decode_access_token(token)


def test_string_subject_is_stripped(auth_secret, monkeypatch) -> None:
    monkeypatch.setattr(time, "time", lambda: 1_000_000)
    token = _sign_payload({"sub": "  user-abc  ", "exp": 1_000_100})
    assert decode_access_token(token)["user_id"] == "user-abc"
