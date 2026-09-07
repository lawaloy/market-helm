"""Deterministic projection backtesting metrics and data loading."""

import json

import pandas as pd
import pytest

from src.analysis.backtesting import backtest_data_dir, evaluate_projections


def _projection(**overrides):
    row = {
        "run_date": "2026-07-02",
        "symbol": "AAPL",
        "current_price": 100.0,
        "target_low": 105.0,
        "target_mid": 110.0,
        "target_high": 115.0,
        "confidence": 80,
        "recommendation": "BUY",
    }
    return {**row, **overrides}


def test_report_tracks_exact_session_coverage_and_calibration():
    projections = [
        _projection(),
        _projection(symbol="MSFT"),
        _projection(symbol=""),
        _projection(run_date="2026-07-09", symbol="NVDA"),
    ]
    closes = [
        {"date": "2026-07-10", "symbol": "AAPL", "close": 108.0},
        {"date": "2026-07-10", "symbol": "NVDA", "close": 150.0},
    ]

    report = evaluate_projections(projections, closes)
    summary = report["summary"]

    assert summary["calendar"] == "XNYS"
    assert summary["horizonSessions"] == 5
    assert summary["projectionCount"] == 4
    assert summary["validProjectionCount"] == 3
    assert summary["sampleCount"] == 1
    assert summary["invalidCount"] == 1
    assert summary["pendingCount"] == 1
    assert summary["missingActualCount"] == 1
    assert summary["evaluationCoveragePct"] == 50.0
    assert summary["directionalAccuracyPct"] == 100.0
    assert summary["bandCoveragePct"] == 100.0
    assert summary["calibrationGapPct"] == -20.0
    assert summary["byConfidenceBand"]["80-89"]["count"] == 1
    assert summary["byRecommendation"]["BUY"]["count"] == 1
    assert report["samples"][0]["targetDate"] == "2026-07-10"
    assert report["samples"][0]["absErrorPct"] == 1.852
    json.dumps(report, allow_nan=False)


def test_missing_target_close_does_not_roll_forward():
    report = evaluate_projections(
        [_projection()],
        [{"date": "2026-07-13", "symbol": "AAPL", "close": 108.0}],
    )

    assert report["summary"]["sampleCount"] == 0
    assert report["summary"]["missingActualCount"] == 1


def test_data_dir_loader_reads_dated_csvs(tmp_path):
    pd.DataFrame([{"symbol": "AAPL", "close": 100.0}]).to_csv(
        tmp_path / "daily_data_2026-07-02.csv", index=False
    )
    pd.DataFrame([{"symbol": "AAPL", "close": 108.0}]).to_csv(
        tmp_path / "daily_data_2026-07-10.csv", index=False
    )
    pd.DataFrame([_projection()]).drop(columns=["run_date"]).to_csv(
        tmp_path / "projections_2026-07-02.csv", index=False
    )

    report = backtest_data_dir(tmp_path)

    assert report["summary"]["sampleCount"] == 1
    assert report["samples"][0]["actual"] == 108.0


def test_empty_data_dir_still_validates_calendar(tmp_path):
    with pytest.raises(ValueError, match="unknown or unavailable"):
        backtest_data_dir(tmp_path, calendar_name="NOT-A-CALENDAR")


def test_sample_limit_is_explicit_and_json_safe():
    projections = [
        _projection(symbol="AAPL"),
        _projection(symbol="MSFT", confidence=float("nan")),
    ]
    closes = [
        {"date": "2026-07-10", "symbol": "AAPL", "close": 108.0},
        {"date": "2026-07-10", "symbol": "MSFT", "close": 108.0},
    ]

    report = evaluate_projections(projections, closes, max_samples=1)

    assert report["summary"]["sampleCount"] == 2
    assert len(report["samples"]) == 1
    assert report["samplesTruncated"] is True
    json.dumps(report, allow_nan=False)
