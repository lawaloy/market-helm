"""Tests for market-helm alerts CLI."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.cli import alerts_commands


def test_cmd_list_prints_rules(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(
        json.dumps(
            {
                "alerts": [
                    {
                        "id": "a1",
                        "name": "Test",
                        "enabled": True,
                        "notifications": ["log"],
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "AAPL",
                            "operator": "less_than",
                            "value": 150,
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
    assert "a1" in text
    assert "enabled" in text


def test_cmd_test_dry_run(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(
        json.dumps(
            {
                "alerts": [
                    {
                        "id": "a1",
                        "name": "Hook",
                        "enabled": True,
                        "notifications": ["webhook"],
                        "webhook_url": "https://hooks.slack.com/services/T000/B000/XXXXXXXX",
                        "webhook_format": "slack",
                        "condition": {"type": "price_threshold", "symbol": "AAPL"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with caplog.at_level("INFO"):
        assert alerts_commands.cmd_test("a1", dry_run=True, config_path=config) == 0
    text = caplog.text
    assert "WebhookNotifier" in text
    assert "MarketHelm alert" in text


def test_cmd_test_missing_id(tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(json.dumps({"alerts": []}), encoding="utf-8")
    assert alerts_commands.cmd_test("missing", config_path=config) == 1
