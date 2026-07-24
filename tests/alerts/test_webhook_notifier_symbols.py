"""Webhook alert text must tolerate dirty symbol lists without TypeError."""

from src.alerts.notifiers.webhook_notifier import WebhookNotifier


def test_alert_text_skips_none_and_blank_symbols() -> None:
    text = WebhookNotifier._alert_text(
        {
            "alert_id": "a1",
            "alert_name": "Watch",
            "symbols": [None, "AAPL", "", "  ", "MSFT"],
            "condition_type": "screening_match",
            "timestamp": "2026-07-24T12:00:00",
        },
        markdown="slack",
    )
    assert "AAPL, MSFT" in text
    assert "None" not in text


def test_alert_text_bare_string_symbol_is_not_character_joined() -> None:
    text = WebhookNotifier._alert_text(
        {
            "alert_id": "a1",
            "symbols": "AAPL",
            "condition_type": "price_threshold",
            "timestamp": "2026-07-24T12:00:00",
        }
    )
    assert "AAPL" in text
    # Character-join of "AAPL" would produce "A, A, P, L"
    assert "A, A, P, L" not in text


def test_alert_text_all_invalid_symbols_shows_none() -> None:
    text = WebhookNotifier._alert_text(
        {
            "alert_id": "a1",
            "symbols": [None, "", "  "],
            "condition_type": "screening_match",
            "timestamp": "2026-07-24T12:00:00",
        }
    )
    assert "(none)" in text


def test_build_payload_discord_tolerates_dirty_symbols() -> None:
    notifier = WebhookNotifier("https://example.com/hook", payload_format="discord")
    payload = notifier.build_payload(
        {
            "alert_id": "x",
            "alert_name": "Drop",
            "symbols": [None, "TSLA"],
            "condition_type": "price_threshold",
            "timestamp": "2026-07-24T12:00:00",
        }
    )
    assert "TSLA" in payload["content"]
    assert "None" not in payload["content"]
