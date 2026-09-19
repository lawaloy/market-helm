"""Summary load failures map to ValueError for missing dates (no JSON files)."""

from pathlib import Path

import pytest

from dashboard.backend.services.data_loader import DataLoader
from tests.helpers.market_bars import seed_summary


def test_load_summary_raises_when_no_summaries(tmp_path: Path) -> None:
    loader = DataLoader(data_dir=tmp_path)
    with pytest.raises(ValueError, match="No summary files found"):
        loader.load_summary()


def test_load_summary_raises_for_missing_date(tmp_path: Path) -> None:
    seed_summary(tmp_path, "2026-01-15", {"date": "2026-01-15", "ai_summary": "ok"})
    loader = DataLoader(data_dir=tmp_path)
    with pytest.raises(ValueError, match="unreadable|not found"):
        loader.load_summary("2099-01-01")


def test_load_summary_accepts_seeded_payload(tmp_path: Path) -> None:
    seed_summary(
        tmp_path,
        "2026-01-15",
        {"date": "2026-01-15", "ai_summary": "Markets mixed."},
    )
    loader = DataLoader(data_dir=tmp_path)

    data = loader.load_summary()
    assert data["ai_summary"] == "Markets mixed."
