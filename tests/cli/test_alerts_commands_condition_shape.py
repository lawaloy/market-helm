"""CLI alerts list/test must soft-fail non-dict condition nests."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from src.cli import alerts_commands


def test_format_condition_soft_fails_non_dict_shapes() -> None:
    assert alerts_commands._format_condition(None) == "?"
    assert alerts_commands._format_condition("price_threshold") == "?"
    assert alerts_commands._format_condition([{"type": "x"}]) == "?"
    assert (
        alerts_commands._format_condition(
            {
                "type": "screening_match",
                "filters": "not-a-dict",
            }
        )
        == "screening: "
    )


def test_cmd_list_survives_null_and_string_conditions(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(
        json.dumps(
            {
                "alerts": [
                    {
                        "id": "a1",
                        "name": "Null condition",
                        "enabled": True,
                        "notifications": "email",
                        "condition": None,
                    },
                    {
                        "id": "a2",
                        "name": "String condition",
                        "enabled": False,
                        "notifications": ["log"],
                        "condition": "price_threshold",
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
    assert "a2" in text
    assert "condition: ?" in text
    # Non-list notifications must not character-join.
    assert "notify: log" in text
    assert "notify: e, m, a, i, l" not in text


def test_run_alert_test_survives_null_condition() -> None:
    """Settings Send test used condition.get and 500'd when condition was null."""
    result = alerts_commands.run_alert_test(
        "a1",
        dry_run=True,
        config={
            "defaults": {},
            "alerts": [
                {
                    "id": "a1",
                    "name": "Broken",
                    "enabled": True,
                    "notifications": ["log"],
                    "condition": None,
                }
            ],
        },
        storage=MagicMock(),
    )
    assert result["status"] == "dry_run"
    assert result["alert_id"] == "a1"
    assert result["previews"]
    assert result["previews"][0]["payload"]["condition_type"] == "test"


def test_run_alert_test_survives_string_condition() -> None:
    result = alerts_commands.run_alert_test(
        "hook",
        dry_run=True,
        config={
            "defaults": {},
            "alerts": [
                {
                    "id": "hook",
                    "name": "Hook",
                    "enabled": True,
                    "notifications": ["log"],
                    "condition": "price_threshold",
                }
            ],
        },
        storage=MagicMock(),
    )
    assert result["status"] == "dry_run"
    assert result["previews"][0]["payload"]["condition_type"] == "test"
