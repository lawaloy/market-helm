"""Demo /api/summary must soft-fail nested non-dict shapes instead of 500ing."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dashboard.backend.api.market import _generate_demo_summary


@pytest.fixture
def temp_data_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def summary_client(temp_data_dir):
    """TestClient with DataLoader pointed at temp_data_dir (summary JSON only)."""
    import pandas as pd
    from dashboard.backend.services.data_loader import DataLoader

    # Daily CSV keeps other endpoints happy if imported; summary path only needs JSON.
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "name": ["Apple"],
            "close": [150.0],
            "change": [1.5],
            "change_percent": [1.0],
            "volume": [1_000_000],
            "index_name": ["S&P 500"],
        }
    ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)

    loader = DataLoader(data_dir=temp_data_dir)
    import dashboard.backend.api.market
    import dashboard.backend.api.projections
    import dashboard.backend.api.stocks
    import dashboard.backend.api.history

    with patch.object(
        dashboard.backend.api.market, "get_data_loader", return_value=loader
    ):
        with patch.object(
            dashboard.backend.api.projections, "get_data_loader", return_value=loader
        ):
            with patch.object(
                dashboard.backend.api.stocks, "get_data_loader", return_value=loader
            ):
                with patch.object(
                    dashboard.backend.api.history, "get_data_loader", return_value=loader
                ):
                    from fastapi.testclient import TestClient
                    from dashboard.backend.main import app

                    yield TestClient(app), temp_data_dir


@pytest.mark.parametrize(
    "analysis,exchange_comparison",
    [
        ("not-a-dict", {}),
        ([{"nested": True}], {}),
        ({"summary": "bad-rollups"}, {}),
        (
            {
                "summary": {"gainers": 1, "losers": 0, "average_change_percent": 1},
                "top_gainers": ["AAPL"],
                "top_losers": "GOOGL",
            },
            {},
        ),
        (
            {
                "summary": {"gainers": 1, "losers": 0, "average_change_percent": 1},
                "top_gainers": {"symbol": "AAPL", "change_percent": 1},
            },
            ["NYSE"],
        ),
    ],
)
def test_generate_demo_summary_soft_fails_nested_shapes(
    analysis, exchange_comparison
) -> None:
    """Truthy non-dict nests previously AttributeError/KeyError'd mid-template."""
    text = _generate_demo_summary(analysis, exchange_comparison)
    assert isinstance(text, str)
    assert "sentiment" in text


def test_generate_demo_summary_skips_string_mover_rows() -> None:
    text = _generate_demo_summary(
        {
            "summary": {"gainers": 2, "losers": 0, "average_change_percent": 1.25},
            "top_gainers": ["AAPL"],
            "top_losers": [None],
        },
        {"S&P 500": {"average_change_percent": 0.8}},
    )
    # Poison first rows must not crash; omit gainer/loser sentences.
    assert "led gains" not in text
    assert "declined" not in text
    assert "S&P 500" in text
    assert "1.25%" in text


def test_api_summary_demo_survives_corrupt_nests(summary_client) -> None:
    """Blank ai_summary + poison analysis/exchange must still return source=demo."""
    client, data_dir = summary_client
    payload = {
        "date": "2026-01-15",
        "ai_summary": "   ",
        "analysis": "corrupt",
        "exchange_comparison": ["NYSE"],
    }
    (data_dir / "summary_2026-01-15.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["date"] == "2026-01-15"
    assert "sentiment" in body["summary"]


def test_api_summary_demo_survives_string_movers(summary_client) -> None:
    client, data_dir = summary_client
    payload = {
        "date": "2026-01-15",
        "analysis": {
            "summary": {"gainers": 1, "losers": 1, "average_change_percent": 0.0},
            "top_gainers": ["AAPL"],
            "top_losers": [{"symbol": "GOOGL", "change_percent": -1.0}],
        },
        "exchange_comparison": {
            "NASDAQ-100": "not-stats",
            "S&P 500": {"average_change_percent": 0.5},
        },
    }
    (data_dir / "summary_2026-01-15.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert "GOOGL" in body["summary"]
    assert "S&P 500" in body["summary"]
