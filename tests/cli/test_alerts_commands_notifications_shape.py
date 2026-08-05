"""CLI alerts list must soft-fail mixed-type notification channel lists."""

import json
from pathlib import Path

from src.cli import alerts_commands


def test_cmd_list_skips_non_string_notification_channels(caplog, tmp_path: Path) -> None:
    """Hand-edited [1, null, "email"] previously TypeError'd on ', '.join(...)."""
    config = tmp_path / "alerts.json"
    config.write_text(
        json.dumps(
            {
                "alerts": [
                    {
                        "id": "a1",
                        "name": "Mixed notify",
                        "enabled": True,
                        "notifications": [1, None, "email", "  ", "log"],
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "AAPL",
                            "operator": "less_than",
                            "value": 150,
                        },
                    },
                    {
                        "id": "a2",
                        "name": "All junk",
                        "enabled": False,
                        "notifications": [None, 0, {}],
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "MSFT",
                            "operator": "greater_than",
                            "value": 1,
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    with caplog.at_level("INFO"):
        assert alerts_commands.cmd_list(config) == 0
    text = caplog.text
    assert "a1" in text
    assert "notify: email, log" in text
    # Empty after filtering non-strings falls back to log (not a crash).
    assert "a2" in text
    assert "notify: log" in text
