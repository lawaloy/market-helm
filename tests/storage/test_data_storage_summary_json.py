"""Regression tests for JSON-safe daily summary writes."""

import math
from datetime import date
from pathlib import Path

import pytest

from src.storage.data_storage import DataStorage, _json_safe_value
from src.storage.projections_store import load_daily_summary


@pytest.fixture
def storage(tmp_path: Path) -> DataStorage:
    return DataStorage(data_dir=str(tmp_path))


def test_json_safe_value_coerces_non_finite_floats() -> None:
    payload = {
        "avg": float("nan"),
        "high": float("inf"),
        "low": float("-inf"),
        "ok": 1.5,
        "nested": [{"volume": float("nan")}, 2.0],
        "keep": "text",
    }

    safe = _json_safe_value(payload)

    assert safe["avg"] is None
    assert safe["high"] is None
    assert safe["low"] is None
    assert safe["ok"] == 1.5
    assert safe["nested"] == [{"volume": None}, 2.0]
    assert safe["keep"] == "text"


def test_save_summary_writes_strict_json_for_nan_and_inf(
    storage: DataStorage, tmp_path: Path
) -> None:
    summary = {
        "analysis": {
            "average_change": float("nan"),
            "top_gainers": [{"symbol": "AAA", "change_percent": float("inf")}],
            "top_volume": [{"symbol": "BBB", "volume": float("-inf")}],
        },
        "projection_summary": {
            "average_confidence": float("nan"),
            "average_expected_change": 1.25,
        },
    }

    location = storage.save_summary(summary, date=date(2026, 7, 24))
    assert location == "summary:2026-07-24"
    assert list(tmp_path.glob("summary_*.json")) == []

    loaded = load_daily_summary("2026-07-24", data_dir=tmp_path)
    assert loaded["date"] == "2026-07-24"
    assert loaded["analysis"]["average_change"] is None
    assert loaded["analysis"]["top_gainers"][0]["change_percent"] is None
    assert loaded["analysis"]["top_volume"][0]["volume"] is None
    assert loaded["projection_summary"]["average_confidence"] is None
    assert loaded["projection_summary"]["average_expected_change"] == 1.25
    assert math.isnan(summary["analysis"]["average_change"])
