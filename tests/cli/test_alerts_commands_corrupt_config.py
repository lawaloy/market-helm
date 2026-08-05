"""CLI alerts list/test must soft-fail on corrupt or non-object configs."""

import json
from pathlib import Path

from src.cli import alerts_commands


def test_cmd_list_soft_fails_on_corrupt_json(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text("{not-json", encoding="utf-8")
    with caplog.at_level("ERROR"):
        assert alerts_commands.cmd_list(config) == 1
    assert "Corrupt or invalid alerts config" in caplog.text


def test_cmd_list_soft_fails_on_non_object_json(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with caplog.at_level("ERROR"):
        assert alerts_commands.cmd_list(config) == 1
    assert "Corrupt or invalid alerts config" in caplog.text


def test_cmd_test_soft_fails_on_corrupt_json(caplog, tmp_path: Path) -> None:
    config = tmp_path / "alerts.json"
    config.write_text("{broken", encoding="utf-8")
    with caplog.at_level("ERROR"):
        assert alerts_commands.cmd_test("a1", dry_run=True, config_path=config) == 1
    assert "Corrupt or invalid alerts config" in caplog.text
