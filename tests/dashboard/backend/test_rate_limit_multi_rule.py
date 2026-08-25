"""Overlapping rate-limit rules must return the tightest remaining bucket."""

from starlette.requests import Request

import dashboard.backend.rate_limit as rate_limit
from dashboard.backend.rate_limit import RateLimitRule, check_rate_limits


def _api_request(path: str = "/api/auth/login", method: str = "POST") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [],
            "client": ("203.0.113.5", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def _enable_memory_limits(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("MARKET_HELM_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setattr(rate_limit, "_memory_counters", rate_limit._MemoryCounters())


def test_allowed_decision_uses_min_remaining_across_matching_rules(monkeypatch) -> None:
    """Login matches a tight auth bucket and a looser global bucket."""
    _enable_memory_limits(monkeypatch)
    rules = (
        RateLimitRule("auth-login", 2, 60, paths=("/api/auth/login",), methods=("POST",)),
        RateLimitRule("api-global", 10, 60),
    )
    now = 1_700_000_000

    first = check_rate_limits(_api_request(), now=now, rules=rules)
    second = check_rate_limits(_api_request(), now=now, rules=rules)

    assert first is not None and first.allowed is True
    assert first.limit == 2
    assert first.remaining == 1
    assert second is not None and second.allowed is True
    assert second.limit == 2
    assert second.remaining == 0


def test_blocked_decision_comes_from_first_exhausted_rule_not_sibling_headroom(
    monkeypatch,
) -> None:
    """A still-open global bucket must not hide an exhausted auth-login bucket."""
    _enable_memory_limits(monkeypatch)
    rules = (
        RateLimitRule("auth-login", 1, 60, paths=("/api/auth/login",), methods=("POST",)),
        RateLimitRule("api-global", 10, 60),
    )
    now = 1_700_000_000

    allowed = check_rate_limits(_api_request(), now=now, rules=rules)
    blocked = check_rate_limits(_api_request(), now=now, rules=rules)

    assert allowed is not None and allowed.allowed is True
    assert allowed.limit == 1
    assert blocked is not None and blocked.allowed is False
    assert blocked.limit == 1
    assert blocked.remaining == 0
