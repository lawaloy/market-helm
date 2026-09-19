"""DataStorage saves must not truncate existing durable rows when a write fails."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage.data_storage import DataStorage
from src.storage.market_bars import load_market_bars
from src.storage.projections_store import load_daily_summary, load_projections


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    return DataStorage(data_dir=str(tmp_path))


def test_save_daily_data_upserts_and_overwrites_bars(storage, tmp_path):
    """save_daily_data writes market_bars; a later upsert replaces the same day."""
    target = date(2026, 6, 9)
    first = storage.save_daily_data(
        [{"symbol": "AAPL", "name": "Apple", "close": 150.0}],
        date=target,
    )
    assert first == "market_bars:2026-06-09"
    rows = load_market_bars(target, data_dir=tmp_path)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["close"] == 150.0

    second = storage.save_daily_data(
        [
            {"symbol": "AAPL", "name": "Apple", "close": 155.0},
            {"symbol": "MSFT", "name": "Microsoft", "close": 400.0},
        ],
        date=target,
    )
    assert second == "market_bars:2026-06-09"
    rows = load_market_bars(target, data_dir=tmp_path)
    by_symbol = {row["symbol"]: row["close"] for row in rows}
    assert by_symbol["AAPL"] == 155.0
    assert by_symbol["MSFT"] == 400.0
    assert list(tmp_path.glob("daily_data_*.csv")) == []


def test_save_summary_upserts_without_json_files(storage, tmp_path):
    target = date(2026, 6, 9)
    location = storage.save_summary({"total_stocks": 2}, date=target)
    assert location == "summary:2026-06-09"
    assert load_daily_summary(target, data_dir=tmp_path)["total_stocks"] == 2
    assert list(tmp_path.glob("summary_*.json")) == []

    storage.save_summary({"total_stocks": 99}, date=target)
    assert load_daily_summary(target, data_dir=tmp_path)["total_stocks"] == 99
    assert list(tmp_path.glob("summary_*.json")) == []
    assert list(tmp_path.glob("summary_*.json.tmp")) == []


def test_save_projections_upserts_without_csv_files(storage, tmp_path):
    target = date(2026, 6, 9)
    location = storage.save_projections(
        {
            "AAPL": {
                "symbol": "AAPL",
                "name": "Apple",
                "current_price": 150.0,
                "target_low": 140.0,
                "target_mid": 155.0,
                "target_high": 170.0,
                "expected_change_percent": 3.0,
                "recommendation": "BUY",
                "confidence": 80,
                "trend": "up",
                "momentum_score": 1.0,
                "volatility_score": 0.2,
                "risk_level": "LOW",
                "reason": "steady",
                "projection_date": "2026-06-14",
                "generated_at": "2026-06-09T12:00:00",
            }
        },
        date=target,
    )
    assert location == "projections:2026-06-09"
    assert load_projections(target, data_dir=tmp_path)[0]["symbol"] == "AAPL"
    assert list(tmp_path.glob("projections_*.csv")) == []

    storage.save_projections(
        {
            "MSFT": {
                "symbol": "MSFT",
                "name": "Microsoft",
                "current_price": 400.0,
                "target_low": 390.0,
                "target_mid": 410.0,
                "target_high": 430.0,
                "expected_change_percent": 2.0,
                "recommendation": "HOLD",
                "confidence": 70,
                "trend": "flat",
                "momentum_score": 0.5,
                "volatility_score": 0.3,
                "risk_level": "MED",
                "reason": "mixed",
                "projection_date": "2026-06-14",
                "generated_at": "2026-06-09T12:00:00",
            }
        },
        date=target,
    )
    symbols = {row["symbol"] for row in load_projections(target, data_dir=tmp_path)}
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert list(tmp_path.glob("projections_*.csv")) == []
    assert (tmp_path / "projections_2026-06-09.md").is_file()


def test_save_projections_still_persists_when_markdown_replace_fails(storage, tmp_path):
    """Optional markdown I/O must not roll back durable projection rows."""
    target = date(2026, 6, 9)
    real_replace = Path.replace

    def boom(self, target_path):
        if self.name.endswith(".md.tmp") or str(target_path).endswith(".md"):
            raise OSError("simulated markdown crash")
        return real_replace(self, target_path)

    with patch.object(Path, "replace", boom):
        # Markdown is best-effort after DB write; failure is swallowed as a warning.
        location = storage.save_projections(
            {
                "AAPL": {
                    "symbol": "AAPL",
                    "name": "Apple",
                    "current_price": 150.0,
                    "target_mid": 155.0,
                    "recommendation": "BUY",
                    "confidence": 80,
                }
            },
            date=target,
        )

    assert location == "projections:2026-06-09"
    assert load_projections(target, data_dir=tmp_path)[0]["symbol"] == "AAPL"
