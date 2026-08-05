"""Summary JSON with NaN/Infinity constants must soft-fail as unreadable."""

from pathlib import Path

import pytest

from dashboard.backend.services.data_loader import DataLoader


@pytest.mark.parametrize(
    "raw",
    [
        '{"date":"2026-01-15","ai_summary":NaN}',
        '{"date":"2026-01-15","ai_summary":Infinity}',
        '{"date":"2026-01-15","ai_summary":-Infinity}',
        '{"date":"2026-01-15","analysis":{"average_change_percent":NaN}}',
    ],
)
def test_load_summary_rejects_nonfinite_json_constants(tmp_path: Path, raw: str) -> None:
    (tmp_path / "summary_2026-01-15.json").write_text(raw, encoding="utf-8")
    loader = DataLoader(data_dir=tmp_path)

    with pytest.raises(ValueError, match="unreadable"):
        loader.load_summary()


def test_load_summary_accepts_strict_json(tmp_path: Path) -> None:
    (tmp_path / "summary_2026-01-15.json").write_text(
        '{"date":"2026-01-15","ai_summary":"Markets mixed."}',
        encoding="utf-8",
    )
    loader = DataLoader(data_dir=tmp_path)

    data = loader.load_summary()
    assert data["ai_summary"] == "Markets mixed."
