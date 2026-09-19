"""Protect the scheduled forward-projection evidence collection contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "schedule.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_projection_evidence_runs_weekdays_after_xnys_close() -> None:
    workflow = _workflow()

    assert workflow.startswith("name: Projection evidence collection\n")
    assert "cron: '30 22 * * 1-5'" in workflow
    assert "group: projection-evidence-collection" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "if: github.ref_name == github.event.repository.default_branch" in workflow
    assert "TZ: America/New_York" in workflow
    assert "scripts/projection_collection_day.py" in workflow
    assert workflow.count("steps.collection-day.outputs.run == 'true'") == 7


def test_projection_evidence_restores_latest_unexpired_successful_archive() -> None:
    workflow = _workflow()

    assert "actions: read" in workflow
    assert "workflow_id: 'schedule.yml'" in workflow
    assert "branch: context.payload.repository.default_branch" in workflow
    assert "status: 'success'" in workflow
    assert "artifact.name === 'projection-forward-archive'" in workflow
    assert "!artifact.expired" in workflow
    assert "uses: actions/download-artifact@v4" in workflow
    assert "path: data" in workflow
    assert "run-id: ${{ steps.previous-archive.outputs.run-id }}" in workflow
    assert "github-token: ${{ github.token }}" in workflow


def test_projection_evidence_preserves_progress_and_qualified_capture() -> None:
    workflow = _workflow()

    assert "scripts/projection_baseline.py assess" in workflow
    assert 'json.load(open("data/projection-assessment.json"))' in workflow
    assert 'assert type(value) is bool' in workflow
    assert 'echo "qualified=$qualified" >> "$GITHUB_OUTPUT"' in workflow
    assert "scripts/projection_baseline.py capture" in workflow
    assert "name: projection-forward-archive" in workflow
    assert "data/market_bars.sqlite" in workflow
    assert "data/projections_*.csv" in workflow
    assert "data/projection-assessment.json" in workflow
    assert "name: projection-observed-baseline-${{ github.run_id }}" in workflow
    assert workflow.count("retention-days: 90") == 2


def test_projection_evidence_requires_fresh_bars_and_projection_files() -> None:
    workflow = _workflow()

    assert 'rm -f "data/projections_${snapshot_date}.csv"' in workflow
    assert "list_market_bar_dates" in workflow
    assert "snapshot_date" in workflow
    assert 'test -s "data/projections_${snapshot_date}.csv"' in workflow
