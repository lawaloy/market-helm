"""Regression coverage for the preserved projection evaluator baseline."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "projection_baseline.py"
SPEC = importlib.util.spec_from_file_location("projection_baseline", MODULE_PATH)
assert SPEC is not None
projection_baseline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(projection_baseline)


def test_committed_projection_baseline_matches_evaluator() -> None:
    assert projection_baseline.check() == 0


def test_projection_baseline_covers_representative_scenarios() -> None:
    report = json.loads(projection_baseline.render_report())
    summary = report["summary"]

    assert summary["projectionCount"] == 10
    assert summary["sampleCount"] == 7
    assert summary["invalidCount"] == 1
    assert summary["pendingCount"] == 1
    assert summary["missingActualCount"] == 1
    assert summary["evaluationCoveragePct"] == 87.5
    assert set(summary["byConfidenceBand"]) == {
        "0-49",
        "50-59",
        "60-69",
        "70-79",
        "80-89",
        "90-100",
        "UNKNOWN",
    }
    assert {sample["directionCorrect"] for sample in report["samples"]} == {
        True,
        False,
    }
    assert {sample["bandHit"] for sample in report["samples"]} == {
        True,
        False,
        None,
    }
    assert [sample["symbol"] for sample in report["samples"][:3]] == [
        "AMZN",
        "NVDA",
        "ORCL",
    ]


def test_projection_baseline_check_reports_drift(tmp_path: Path, monkeypatch) -> None:
    stale_report = tmp_path / "report.json"
    stale_report.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(projection_baseline, "REPORT_PATH", stale_report)

    assert projection_baseline.check() == 1


def _qualified_report() -> dict:
    samples = [
        {
            "runDate": f"2026-01-{index % 20 + 1:02d}",
            "symbol": f"S{index % 25:02d}",
            "actualProvenance": "verified_quote_session",
            "generationProvenance": "timestamped",
        }
        for index in range(200)
    ]
    return {
        "summary": {
            "sampleCount": 200,
            "verifiedOutcomeCount": 200,
            "timestampedProjectionCount": 200,
            "evaluationCoveragePct": 95.0,
            "byConfidenceBand": {
                "60-69": {"count": 100},
                "70-79": {"count": 100},
            },
        },
        "samples": samples,
        "samplesTruncated": False,
    }


def test_observed_baseline_qualification_requires_provenance_and_diversity() -> None:
    assessment = projection_baseline.qualify_report(_qualified_report())

    assert assessment["qualified"] is True
    assert assessment["failures"] == []


def test_observed_baseline_qualification_fails_closed() -> None:
    report = _qualified_report()
    report["summary"]["verifiedOutcomeCount"] = 199
    report["samplesTruncated"] = True

    assessment = projection_baseline.qualify_report(report)

    assert assessment["qualified"] is False
    assert "report samples are truncated" in assessment["failures"]
    assert any("verified quote-session" in failure for failure in assessment["failures"])


def test_capture_refuses_unqualified_data_without_creating_output(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        projection_baseline,
        "observed_report",
        lambda *_args, **_kwargs: {
            "summary": {"sampleCount": 0, "evaluationCoveragePct": None},
            "samples": [],
            "samplesTruncated": False,
        },
    )
    output = tmp_path / "observed-v1"

    assert projection_baseline.capture(tmp_path, output, 365) == 1
    assert not output.exists()
