"""CORS_ORIGINS parsing must reject wildcards and unsafe schemes."""

from dashboard.backend.main import DEFAULT_CORS_ORIGINS, parse_cors_origins


def test_parse_cors_origins_falls_back_when_empty() -> None:
    assert parse_cors_origins("") == DEFAULT_CORS_ORIGINS
    assert parse_cors_origins("   ,  ") == DEFAULT_CORS_ORIGINS


def test_parse_cors_origins_accepts_explicit_http_origins() -> None:
    assert parse_cors_origins(
        "https://app.example.com, http://localhost:3000"
    ) == ["https://app.example.com", "http://localhost:3000"]


def test_parse_cors_origins_rejects_wildcard_with_credentials() -> None:
    assert parse_cors_origins("*") == DEFAULT_CORS_ORIGINS
    assert parse_cors_origins("*, https://ok.example.com") == [
        "https://ok.example.com"
    ]


def test_parse_cors_origins_rejects_non_http_schemes() -> None:
    assert parse_cors_origins("javascript:alert(1)") == DEFAULT_CORS_ORIGINS
    assert parse_cors_origins("data:text/html,hi") == DEFAULT_CORS_ORIGINS
    assert parse_cors_origins(
        "ftp://files.example.com, https://ok.example.com"
    ) == ["https://ok.example.com"]


def test_parse_cors_origins_rejects_control_and_internal_whitespace() -> None:
    assert parse_cors_origins("https://evil.example.com\nhttps://ok.example.com") == (
        DEFAULT_CORS_ORIGINS
    )
    assert parse_cors_origins("https://evil example.com") == DEFAULT_CORS_ORIGINS


def test_parse_cors_origins_custom_defaults() -> None:
    defaults = ["https://fallback.example.com"]
    assert parse_cors_origins("*", defaults=defaults) == defaults
