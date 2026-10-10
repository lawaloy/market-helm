"""CLI behavior for the legacy market-data backfill."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backfill_market_data.py"
SPEC = importlib.util.spec_from_file_location("backfill_market_data", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
backfill_market_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backfill_market_data)


def test_cli_reports_successful_import(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MARKETHELM_DATABASE_URL", raising=False)
    (tmp_path / "daily_data_2026-09-18.csv").write_text(
        "symbol,close\nAAPL,150\n", encoding="utf-8"
    )

    assert backfill_market_data.main(["--data-dir", str(tmp_path)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["daily_data"]["rows_written"] == 1


def test_cli_returns_failure_when_a_file_is_malformed(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MARKETHELM_DATABASE_URL", raising=False)
    (tmp_path / "summary_2026-09-18.json").write_text("[]", encoding="utf-8")

    assert backfill_market_data.main(["--data-dir", str(tmp_path)]) == 1

    report = json.loads(capsys.readouterr().out)
    assert report["errors"][0]["file"] == "summary_2026-09-18.json"


def test_cli_returns_failure_for_missing_data_dir(tmp_path, capsys):
    missing = tmp_path / "missing"

    assert backfill_market_data.main(["--data-dir", str(missing)]) == 1

    report = json.loads(capsys.readouterr().err)
    assert "Data directory not found" in report["errors"][0]["error"]
