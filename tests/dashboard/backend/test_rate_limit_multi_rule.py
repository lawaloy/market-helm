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


def test_blocked_global_not_hidden_by_path_rule_at_exact_limit(monkeypatch) -> None:
    """An allowed sibling at remaining==0 must not hide a blocked global bucket.

    ``remaining`` is 0 both at ``count == limit`` (still allowed) and
    ``count > limit`` (blocked). ``min(remaining)`` would pick the first
    remaining-0 decision — here the still-allowed login rule — and skip
    429 even though the global bucket is already exhausted. Operators can
    set ``MARKET_HELM_RATE_LIMIT_GLOBAL`` tighter than a path rule.
    """
    _enable_memory_limits(monkeypatch)
    rules = (
        RateLimitRule(
            "auth-login", 2, 60, paths=("/api/auth/login",), methods=("POST",)
        ),
        RateLimitRule("api-global", 1, 60),
    )
    now = 1_700_000_000

    first = check_rate_limits(_api_request(), now=now, rules=rules)
    blocked = check_rate_limits(_api_request(), now=now, rules=rules)

    assert first is not None and first.allowed is True
    assert first.limit == 1
    assert first.remaining == 0
    assert blocked is not None and blocked.allowed is False
    assert blocked.limit == 1
    assert blocked.remaining == 0


def test_unmatched_path_does_not_consume_path_specific_rule(monkeypatch) -> None:
    """GET /api/test must not increment the auth-login bucket.

    If ``check_rate_limits`` dropped the ``continue`` on non-matching rules,
    every API call would consume login/register/expensive buckets and exhaust
    them for the real endpoints.
    """
    _enable_memory_limits(monkeypatch)
    rules = (
        RateLimitRule(
            "auth-login", 1, 60, paths=("/api/auth/login",), methods=("POST",)
        ),
        RateLimitRule("api-global", 10, 60),
    )
    now = 1_700_000_000

    for _ in range(2):
        decision = check_rate_limits(
            _api_request("/api/test", method="GET"), now=now, rules=rules
        )
        assert decision is not None and decision.allowed is True
        assert decision.limit == 10

    login = check_rate_limits(
        _api_request("/api/auth/login", method="POST"), now=now, rules=rules
    )
    assert login is not None and login.allowed is True
    assert login.limit == 1
    assert login.remaining == 0


def test_check_rate_limits_returns_none_when_no_rule_matches(monkeypatch) -> None:
    """Unmatched API paths must pass through — not 429 or crash on min([])."""
    _enable_memory_limits(monkeypatch)
    rules = (
        RateLimitRule(
            "auth-login", 1, 60, paths=("/api/auth/login",), methods=("POST",)
        ),
    )
    now = 1_700_000_000

    decision = check_rate_limits(
        _api_request("/api/test", method="GET"), now=now, rules=rules
    )
    assert decision is None
