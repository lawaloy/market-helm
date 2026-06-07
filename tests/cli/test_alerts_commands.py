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


@patch("src.alerts.notifiers.webhook_notifier.requests.post")
def test_cmd_test_returns_error_when_live_delivery_fails(
    mock_post: MagicMock,
    tmp_path: Path,
) -> None:
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "err"
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

    assert alerts_commands.cmd_test("a1", config_path=config) == 1


def test_cmd_test_missing_id(tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(json.dumps({"alerts": []}), encoding="utf-8")
    assert alerts_commands.cmd_test("missing", config_path=config) == 1


@patch("src.alerts.alert_worker.run_worker_once")
def test_cmd_run_once(mock_once) -> None:
    mock_once.return_value = {"triggered": 0, "last_data_date": "2026-05-20"}
    assert alerts_commands.cmd_run(loop=False) == 0
    mock_once.assert_called_once()


@patch("src.alerts.alert_worker.run_worker_loop")
def test_cmd_run_loop(mock_loop) -> None:
    assert alerts_commands.cmd_run(loop=True, interval=120) == 0
    mock_loop.assert_called_once_with(120)
