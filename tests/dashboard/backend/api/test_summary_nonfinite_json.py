"""/api/summary must not 500 on non-finite JSON or non-string ai_summary."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.helpers.market_bars import seed_simple_bars


@pytest.fixture
def summary_client(monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    tmp = tempfile.mkdtemp()
    data_dir = Path(tmp)
    from dashboard.backend.services.data_loader import DataLoader

    seed_simple_bars(
        data_dir,
        "2026-01-15",
        close=150.0,
        change=1.5,
        change_percent=1.0,
        volume=1_000_000,
        name="Apple",
        index_name="S&P 500",
    )

    loader = DataLoader(data_dir=data_dir)
    import dashboard.backend.api.history
    import dashboard.backend.api.market
    import dashboard.backend.api.projections
    import dashboard.backend.api.stocks

    with patch.object(dashboard.backend.api.market, "get_data_loader", return_value=loader):
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

                    try:
                        yield TestClient(app), data_dir
                    finally:
                        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize(
    "raw",
    [
        '{"date":"2026-01-15","ai_summary":NaN}',
        '{"date":"2026-01-15","ai_summary":Infinity}',
    ],
)
def test_api_summary_nonfinite_json_returns_404(summary_client, raw: str) -> None:
    client, data_dir = summary_client
    (data_dir / "summary_2026-01-15.json").write_text(raw, encoding="utf-8")

    response = client.get("/api/summary")
    assert response.status_code == 404
    assert response.json()["detail"] == "No data available."


def test_api_summary_non_string_ai_summary_falls_back_to_demo(summary_client) -> None:
    """Truthy non-string ai_summary must not AttributeError on .strip()."""
    client, data_dir = summary_client
    payload = {
        "date": "2026-01-15",
        "ai_summary": 12345,
        "analysis": {
            "summary": {"gainers": 1, "losers": 0, "average_change_percent": 1.0},
            "top_gainers": [],
            "top_losers": [],
        },
        "exchange_comparison": {},
    }
    (data_dir / "summary_2026-01-15.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert isinstance(body["summary"], str)
