"""Projection markdown must tolerate None/NaN reason and price cells."""

from datetime import date
from pathlib import Path

import pandas as pd

from src.storage.data_storage import DataStorage, _md_money, _md_reason


def _projection_row(**overrides):
    row = {
        "symbol": "AAPL",
        "name": "Apple",
        "current_price": 180.0,
        "target_low": 175.0,
        "target_mid": 185.0,
        "target_high": 195.0,
        "expected_change_percent": 2.5,
        "recommendation": "STRONG BUY",
        "confidence": 90,
        "trend": "Bullish",
        "momentum_score": 0.8,
        "volatility_score": 0.2,
        "risk_level": "Low",
        "reason": "Strong momentum",
        "projection_date": "2026-05-25",
        "generated_at": "2026-05-20T12:00:00",
    }
    row.update(overrides)
    return row


def test_md_reason_handles_none_nan_and_truncation() -> None:
    assert _md_reason(None, 55) == ""
    assert _md_reason(float("nan"), 55) == ""
    assert _md_reason("short", 55) == "short"
    assert _md_reason("x" * 60, 55) == ("x" * 55) + "..."


def test_md_money_handles_none_nan_inf() -> None:
    assert _md_money(12.5) == "$12.50"
    assert _md_money(None) == "—"
    assert _md_money(float("nan")) == "—"
    assert _md_money(float("inf")) == "—"


def test_save_projections_writes_markdown_with_null_reason_and_prices(tmp_path) -> None:
    """None/NaN reason or prices previously TypeError'd and dropped the .md file."""
    storage = DataStorage(data_dir=str(tmp_path))
    projections = {
        "AAPL": _projection_row(reason=None, current_price=None, target_mid=float("nan")),
        "MSFT": _projection_row(
            symbol="MSFT",
            recommendation="BUY",
            confidence=70,
            reason=float("nan"),
            expected_change_percent=float("inf"),
        ),
    }

    csv_path = Path(storage.save_projections(projections, date=date(2026, 5, 20)))
    md_path = csv_path.with_suffix(".md")

    assert csv_path.exists()
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "Stock Market Projections Report" in text
    assert "**AAPL**" in text
    assert "**MSFT**" in text
    assert "—" in text


def test_generate_projection_markdown_with_all_nan_averages(tmp_path) -> None:
    """All-NaN rollup means must not abort markdown generation."""
    storage = DataStorage(data_dir=str(tmp_path))
    df = pd.DataFrame(
        [
            _projection_row(
                expected_change_percent=float("nan"),
                confidence=float("nan"),
                reason=None,
            )
        ]
    )
    md_path = tmp_path / "projections_nan.md"
    storage._generate_projection_markdown(df, md_path, date(2026, 5, 20))

    text = md_path.read_text(encoding="utf-8")
    assert "Expected Market Direction:** —" in text
    assert "Average Confidence Level:** —" in text
    assert "Market Sentiment:** Neutral" in text
