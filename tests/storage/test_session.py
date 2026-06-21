"""Unit tests for signed access tokens."""

import time

import pytest

from src.storage.session import AuthError, create_access_token, decode_access_token


@pytest.fixture
def auth_secret(monkeypatch):
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")


class TestSession:
    def test_create_and_decode_token(self, auth_secret):
        token = create_access_token("user-123")
        payload = decode_access_token(token)
        assert payload["user_id"] == "user-123"

    def test_expired_token_rejected(self, auth_secret, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: 1_000_000)
        token = create_access_token("user-123", ttl_seconds=1)
        monkeypatch.setattr(time, "time", lambda: 1_000_010)
        with pytest.raises(AuthError, match="expired"):
            decode_access_token(token)

    def test_invalid_signature_rejected(self, auth_secret):
        token = create_access_token("user-123")
        tampered = token[:-4] + "xxxx"
        with pytest.raises(AuthError):
            decode_access_token(tampered)

    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.delenv("MARKET_HELM_AUTH_SECRET", raising=False)
        with pytest.raises(AuthError, match="MARKET_HELM_AUTH_SECRET"):
            create_access_token("user-123")
