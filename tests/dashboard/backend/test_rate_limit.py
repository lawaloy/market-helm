"""Production API rate-limit middleware tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import dashboard.backend.rate_limit as rate_limit
from dashboard.backend.rate_limit import RateLimitMiddleware, RateLimitRule, client_ip


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/test")
    async def api_test():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


def _api_request(path: str, method: str = "GET", peer: str = "203.0.113.5") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [],
            "client": (peer, 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def _request(peer: str, forwarded: str = "") -> Request:
    headers = []
    if forwarded:
        headers.append((b"x-forwarded-for", forwarded.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "raw_path": b"/api/test",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_middleware_returns_standard_limit_headers_and_429(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setattr(
        rate_limit,
        "configured_rules",
        lambda: (RateLimitRule("test", 2, 60),),
    )
    monkeypatch.setattr(rate_limit, "_memory_counters", rate_limit._MemoryCounters())
    client = TestClient(_app())

    first = client.get("/api/test")
    second = client.get("/api/test")
    blocked = client.get("/api/test")

    assert first.status_code == 200
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert second.headers["x-ratelimit-remaining"] == "0"
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Too many requests."}
    assert int(blocked.headers["retry-after"]) >= 1


def test_non_api_routes_are_not_limited(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setattr(
        rate_limit,
        "configured_rules",
        lambda: (RateLimitRule("test", 1, 60),),
    )
    client = TestClient(_app())

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200


def test_forwarded_header_ignored_from_untrusted_peer(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    assert client_ip(_request("203.0.113.5", "198.51.100.7")) == "203.0.113.5"


def test_forwarded_chain_uses_first_untrusted_hop_from_right(monkeypatch) -> None:
    monkeypatch.setenv(
        "MARKET_HELM_TRUSTED_PROXY_CIDRS", "10.0.0.0/8,192.0.2.0/24"
    )
    request = _request("10.0.0.5", "198.51.100.9, 192.0.2.10")
    assert client_ip(request) == "198.51.100.9"


def test_backend_failure_returns_503(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:///unused.db")
    monkeypatch.setattr(
        rate_limit,
        "configured_rules",
        lambda: (RateLimitRule("test", 1, 60),),
    )

    def fail(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(rate_limit, "consume_rate_limit", fail)
    response = TestClient(_app()).get("/api/test")
    assert response.status_code == 503
    assert response.json() == {"detail": "Rate-limit service unavailable."}


def test_invalid_enabled_value_falls_back_to_hosted_default(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:///hosted.db")
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_ENABLED", "maybe")
    assert rate_limit.rate_limiting_enabled() is True


def test_invalid_forwarded_hop_falls_back_to_peer(monkeypatch) -> None:
    """Garbage X-Forwarded-For from a trusted proxy must not skip to a later hop."""
    monkeypatch.setenv("MARKET_HELM_TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    assert client_ip(_request("10.0.0.5", "not-an-ip, 198.51.100.9")) == "10.0.0.5"


def test_poisoned_rate_limit_env_clamps_to_safe_bounds(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_REGISTER", "999999999")
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_LOGIN", "not-a-number")
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_GLOBAL", "0")
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_EXPENSIVE", "-5")
    rules = {rule.name: rule for rule in rate_limit.configured_rules()}
    assert rules["auth-register"].limit == 1000
    assert rules["auth-login"].limit == 10
    assert rules["api-global"].limit == 1
    assert rules["expensive-write"].limit == 1


def test_expensive_write_rule_covers_account_mutations() -> None:
    rules = {rule.name: rule for rule in rate_limit.configured_rules()}
    expensive = rules["expensive-write"]
    assert expensive.matches(
        _api_request("/api/auth/password/change", method="POST")
    )
    assert expensive.matches(_api_request("/api/auth/account", method="DELETE"))
    assert not expensive.matches(_api_request("/api/auth/account", method="GET"))
    assert not expensive.matches(_api_request("/api/alerts/quotes", method="GET"))


def test_invalid_proxy_value_is_not_logged(monkeypatch, caplog) -> None:
    secret_value = "invalid-secret-proxy-value"
    monkeypatch.setenv("MARKET_HELM_TRUSTED_PROXY_CIDRS", secret_value)
    assert client_ip(_request("203.0.113.5")) == "203.0.113.5"
    assert secret_value not in caplog.text
