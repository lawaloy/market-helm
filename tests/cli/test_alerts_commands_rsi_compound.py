"""CLI alerts list must print RSI and compound condition strings."""

import json
from pathlib import Path

from src.cli import alerts_commands


def test_format_condition_rsi_and_compound_shapes() -> None:
    assert (
        alerts_commands._format_condition(
            {
                "type": "rsi_threshold",
                "symbol": "AAPL",
                "period": 21,
                "operator": "less_than",
                "value": 30,
            }
        )
        == "AAPL RSI(21) less_than 30"
    )
    assert (
        alerts_commands._format_condition(
            {
                "type": "rsi_threshold",
                "symbol": "MSFT",
                "operator": "greater_than",
                "value": 70,
            }
        )
        == "MSFT RSI(14) greater_than 70"
    )
    assert (
        alerts_commands._format_condition(
            {
                "type": "compound",
                "op": "and",
                "conditions": [
                    {"type": "price_threshold", "symbol": "AAPL"},
                    {"type": "rsi_threshold", "symbol": "AAPL"},
                ],
            }
        )
        == "compound and (2 conditions)"
    )
    assert (
        alerts_commands._format_condition({"type": "compound"})
        == "compound and (0 conditions)"
    )


def test_cmd_list_prints_rsi_and_compound_conditions(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(
        json.dumps(
            {
                "alerts": [
                    {
                        "id": "rsi1",
                        "name": "AAPL RSI",
                        "enabled": True,
                        "notifications": ["log"],
                        "condition": {
                            "type": "rsi_threshold",
                            "symbol": "AAPL",
                            "period": 14,
                            "operator": "less_than",
                            "value": 30,
                        },
                    },
                    {
                        "id": "cmp1",
                        "name": "AAPL combo",
                        "enabled": False,
                        "notifications": ["log"],
                        "condition": {
                            "type": "compound",
                            "op": "or",
                            "conditions": [
                                {
                                    "type": "price_threshold",
                                    "symbol": "AAPL",
                                    "operator": "less_than",
                                    "value": 150,
                                },
                                {
                                    "type": "rsi_threshold",
                                    "symbol": "AAPL",
                                    "operator": "less_than",
                                    "value": 30,
                                },
                            ],
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
    assert "rsi1" in text
    assert "cmp1" in text
    assert "condition: AAPL RSI(14) less_than 30" in text
    assert "condition: compound or (2 conditions)" in text
