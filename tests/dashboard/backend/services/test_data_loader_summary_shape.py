"""load_summary must reject non-object JSON so market summary stays 404 not 500."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def loader(temp_data_dir):
    from dashboard.backend.services.data_loader import DataLoader

    return DataLoader(data_dir=temp_data_dir)


@pytest.mark.parametrize("payload", [None, [], "summary", 42])
def test_load_summary_raises_on_non_object_json(loader, temp_data_dir, payload) -> None:
    (temp_data_dir / "summary_2026-01-15.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unreadable"):
        loader.load_summary()


def test_load_summary_still_returns_object(loader, temp_data_dir) -> None:
    summary = {"date": "2026-01-15", "ai_summary": "ok"}
    (temp_data_dir / "summary_2026-01-15.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    assert loader.load_summary() == summary
