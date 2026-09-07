"""Projection backtest CLI behavior."""

import json

import pandas as pd
import pytest

from src.cli.backtest_commands import main


def test_backtest_cli_writes_strict_json_report(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{"symbol": "AAPL", "close": 100.0}]).to_csv(
        data_dir / "daily_data_2026-07-02.csv", index=False
    )
    pd.DataFrame([{"symbol": "AAPL", "close": 108.0}]).to_csv(
        data_dir / "daily_data_2026-07-10.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "current_price": 100.0,
                "target_low": 105.0,
                "target_mid": 110.0,
                "target_high": 115.0,
                "confidence": 80,
                "recommendation": "BUY",
            }
        ]
    ).to_csv(data_dir / "projections_2026-07-02.csv", index=False)
    output = tmp_path / "reports" / "backtest.json"

    assert main(["--data-dir", str(data_dir), "--output", str(output)]) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"]["sampleCount"] == 1
    assert report["summary"]["horizonSessions"] == 5


def test_backtest_cli_rejects_unknown_calendar_even_without_rows(tmp_path):
    with pytest.raises(SystemExit, match="2"):
        main(["--data-dir", str(tmp_path), "--calendar", "NOT-A-CALENDAR"])
