"""Tests for the scheduled projection collection-day guard."""

from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "projection_collection_day.py"
SPEC = importlib.util.spec_from_file_location("projection_collection_day", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
projection_collection_day = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(projection_collection_day)


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-09-14T19:59:00+00:00", False),
        ("2026-09-14T20:01:00+00:00", True),
        ("2026-07-03T22:30:00+00:00", False),
        ("2026-09-13T22:30:00+00:00", False),
    ],
)
def test_session_has_completed(timestamp: str, expected: bool) -> None:
    parsed = datetime.fromisoformat(timestamp)

    assert projection_collection_day.session_has_completed(parsed) is expected


def test_session_has_completed_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone"):
        projection_collection_day.session_has_completed(datetime(2026, 9, 14, 22, 30))


def test_main_prints_machine_readable_boolean(capsys) -> None:
    assert projection_collection_day.main(["--at", "2026-09-14T22:30:00Z"]) == 0
    assert capsys.readouterr().out == "true\n"
