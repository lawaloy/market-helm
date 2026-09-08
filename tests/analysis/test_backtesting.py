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
    assert report["samples"][0]["actualProvenance"] == "legacy_filename"


def test_data_dir_uses_verified_outcome_session_instead_of_filename(tmp_path):
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "close": 108.0,
                "outcome_session": "2026-07-10",
                "outcome_final": True,
            }
        ]
    ).to_csv(tmp_path / "daily_data_2026-07-12.csv", index=False)
    pd.DataFrame(
        [_projection(generated_at="2026-07-02T21:00:00+00:00")]
    ).drop(columns=["run_date"]).to_csv(
        tmp_path / "projections_2026-07-02.csv", index=False
    )

    report = backtest_data_dir(tmp_path)

    assert report["summary"]["sampleCount"] == 1
    assert report["summary"]["verifiedOutcomeCount"] == 1
    assert report["summary"]["timestampedProjectionCount"] == 1
    assert report["samples"][0]["actualDate"] == "2026-07-10"
    assert report["samples"][0]["actualProvenance"] == "verified_quote_session"


def test_data_dir_excludes_intraday_outcomes_with_provenance_columns(tmp_path):
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "close": 108.0,
                "outcome_session": "",
                "outcome_final": False,
            }
        ]
    ).to_csv(tmp_path / "daily_data_2026-07-10.csv", index=False)
    pd.DataFrame([_projection()]).drop(columns=["run_date"]).to_csv(
        tmp_path / "projections_2026-07-02.csv", index=False
    )

    report = backtest_data_dir(tmp_path)

    assert report["summary"]["sampleCount"] == 0
    assert report["summary"]["pendingCount"] == 1


def test_timezone_aware_generation_time_controls_exact_target_session():
    projection = _projection(generated_at="2026-07-06T12:00:00+00:00")
    closes = [
        {"date": "2026-07-10", "symbol": "AAPL", "close": 108.0},
        {"date": "2026-07-13", "symbol": "AAPL", "close": 109.0},
    ]

    report = evaluate_projections([projection], closes)

    assert report["samples"][0]["targetDate"] == "2026-07-10"
    assert report["samples"][0]["actual"] == 108.0


def test_projection_only_archive_preserves_counts(tmp_path):
    pd.DataFrame(
        [
            _projection(),
            _projection(symbol="", target_mid=120.0),
        ]
    ).drop(columns=["run_date"]).to_csv(
        tmp_path / "projections_2026-07-02.csv", index=False
    )

    report = backtest_data_dir(tmp_path)

    assert report["summary"]["projectionCount"] == 2
    assert report["summary"]["validProjectionCount"] == 1
    assert report["summary"]["pendingCount"] == 1
    assert report["summary"]["invalidCount"] == 1
    assert report["summary"]["sampleCount"] == 0


def test_empty_data_dir_still_validates_calendar(tmp_path):
    with pytest.raises(ValueError, match="unknown or unavailable"):
        backtest_data_dir(tmp_path, calendar_name="NOT-A-CALENDAR")


def test_sample_limit_returns_newest_rows_and_is_json_safe():
    projections = [
        _projection(symbol="AAPL"),
        _projection(
            run_date="2026-07-06", symbol="MSFT", confidence=float("nan")
        ),
    ]
    closes = [
        {"date": "2026-07-10", "symbol": "AAPL", "close": 108.0},
        {"date": "2026-07-13", "symbol": "MSFT", "close": 108.0},
    ]

    report = evaluate_projections(projections, closes, max_samples=1)

    assert report["summary"]["sampleCount"] == 2
    assert len(report["samples"]) == 1
    assert report["samples"][0]["symbol"] == "MSFT"
    assert report["samples"][0]["runDate"] == "2026-07-06"
    assert report["samplesTruncated"] is True
    json.dumps(report, allow_nan=False)
