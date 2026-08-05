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
