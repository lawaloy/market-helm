"""CLI alerts list must print screening_match filter strings."""

import json
from pathlib import Path

from src.cli import alerts_commands


def test_format_condition_screening_match_lists_filters() -> None:
    assert (
        alerts_commands._format_condition(
            {
                "type": "screening_match",
                "filters": {"min_volume": 1_000_000, "min_score": 70},
            }
        )
        == "screening: min_volume=1000000, min_score=70"
    )
    assert alerts_commands._format_condition({"type": "screening_match"}) == "screening: "


def test_cmd_list_prints_screening_match_condition(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(
        json.dumps(
            {
                "alerts": [
                    {
                        "id": "scr1",
                        "name": "Volume screen",
                        "enabled": True,
                        "notifications": ["log"],
                        "condition": {
                            "type": "screening_match",
                            "filters": {"min_volume": 1_000_000, "min_score": 70},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with caplog.at_level("INFO"):
        assert alerts_commands.cmd_list(config) == 0
    text = caplog.text
    assert "scr1" in text
    assert "condition: screening: min_volume=1000000, min_score=70" in text
