"""format_alert_email must tolerate dirty symbol payloads without TypeError."""

from src.alerts.notifiers.email_delivery import _format_symbols, format_alert_email


def test_format_symbols_skips_none_and_blank() -> None:
    assert _format_symbols([None, "AAPL", "", "  ", "MSFT"]) == "AAPL, MSFT"
    assert _format_symbols([None, "", "  "]) == "(none)"
    assert _format_symbols(None) == "(none)"
    assert _format_symbols([]) == "(none)"


def test_format_symbols_bare_string_is_not_character_joined() -> None:
    assert _format_symbols("AAPL") == "AAPL"
    assert _format_symbols("  ") == "(none)"


def test_format_symbols_non_iterable_junk() -> None:
    assert _format_symbols(123) == "123"
    assert _format_symbols({"AAPL": 1}) == "{'AAPL': 1}"


def test_format_alert_email_survives_dirty_symbols() -> None:
    _, body = format_alert_email(
        {
            "alert_id": "a1",
            "alert_name": "Watch",
            "symbols": [None, "AAPL", "", 5],
            "condition_type": "screening_match",
            "timestamp": "2026-07-24T12:00:00",
        }
    )
    assert "Symbols: AAPL, 5" in body
    assert "None" not in body
    # Character-join of a bare string would produce "A, A, P, L"
    assert "A, A, P, L" not in body


def test_format_alert_email_bare_string_and_non_list() -> None:
    _, body_str = format_alert_email({"alert_id": "a1", "symbols": "AAPL"})
    assert "Symbols: AAPL" in body_str
    assert "A, A, P, L" not in body_str

    _, body_int = format_alert_email({"alert_id": "a1", "symbols": 99})
    assert "Symbols: 99" in body_int
