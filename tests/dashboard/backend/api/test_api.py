"""Tests for dashboard backend API endpoints."""

import tempfile
import shutil
import json
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def temp_data_dir():
    """Create temp data directory with sample files."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_daily_data(temp_data_dir):
    """Create sample daily_data CSV."""
    df = pd.DataFrame({
        "symbol": ["AAPL", "GOOGL", "MSFT"],
        "name": ["Apple", "Alphabet", "Microsoft"],
        "close": [150.0, 2800.0, 350.0],
        "change": [1.5, -28.0, 2.1],
        "change_percent": [1.0, -1.0, 0.6],
        "volume": [50_000_000, 2_000_000, 25_000_000],
        "index_name": ["S&P 500", "NASDAQ-100", "S&P 500"],
    })
    df.to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
    return temp_data_dir / "daily_data_2026-01-15.csv"


@pytest.fixture
def sample_summary(temp_data_dir):
    """Create sample summary JSON."""
    summary = {
        "date": "2026-01-15",
        "analysis": {
            "date": "2026-01-15",
            "summary": {
                "total_stocks": 3,
                "gainers": 2,
                "losers": 1,
                "average_change_percent": 0.2,
            },
            "top_gainers": [
                {"symbol": "AAPL", "change_percent": 1.0},
                {"symbol": "MSFT", "change_percent": 0.6},
            ],
            "top_losers": [
                {"symbol": "GOOGL", "change_percent": -1.0},
            ],
        },
        "exchange_comparison": {
            "S&P 500": {"average_change_percent": 0.8, "gainers": 2, "losers": 1},
            "NASDAQ-100": {"average_change_percent": -0.2, "gainers": 1, "losers": 1},
        },
    }
    path = temp_data_dir / "summary_2026-01-15.json"
    with open(path, "w") as f:
        json.dump(summary, f)
    return path


@pytest.fixture
def mock_data_loader(temp_data_dir, sample_daily_data, sample_summary):
    """Create a real DataLoader with temp data."""
    from dashboard.backend.services.data_loader import DataLoader
    return DataLoader(data_dir=temp_data_dir)


@pytest.fixture
def client(mock_data_loader):
    """Create TestClient with patched data loader.

    Import API modules first so they exist in the package namespace, then patch
    get_data_loader where it is used. Patches must be where the name is looked up
    (in the using module), not where it is defined.
    """
    import dashboard.backend.api.market
    import dashboard.backend.api.projections
    import dashboard.backend.api.stocks
    import dashboard.backend.api.history
    with patch.object(dashboard.backend.api.market, "get_data_loader", return_value=mock_data_loader):
        with patch.object(dashboard.backend.api.projections, "get_data_loader", return_value=mock_data_loader):
            with patch.object(dashboard.backend.api.stocks, "get_data_loader", return_value=mock_data_loader):
                with patch.object(dashboard.backend.api.history, "get_data_loader", return_value=mock_data_loader):
                    from fastapi.testclient import TestClient
                    from dashboard.backend.main import app
                    yield TestClient(app)


class TestDashboardHealth:
    """Test health and root endpoints."""

    def test_root_returns_spa_or_health_json(self, client):
        """Root serves bundled SPA (HTML) or JSON when SPA is not built."""
        r = client.get("/")
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            data = r.json()
            assert data["status"] == "healthy"
            assert "Stock Exchange Tracker" in data["service"]
        else:
            assert "text/html" in ct

    def test_health_returns_healthy(self, client):
        """Health endpoint returns healthy."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "healthy"}


class TestMarketAPI:
    """Test market API endpoints."""

    def test_market_overview_returns_data(self, client):
        """GET /api/market/overview returns market stats."""
        r = client.get("/api/market/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["totalStocks"] == 3
        assert data["gainers"] == 2
        assert data["losers"] == 1
        assert "date" in data

    def test_market_movers_gainers(self, client):
        """GET /api/market/movers?type=gainers returns top gainers."""
        r = client.get("/api/market/movers", params={"type": "gainers", "limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "gainers"
        assert len(data["data"]) >= 1

    def test_market_movers_losers(self, client):
        """GET /api/market/movers?type=losers returns top losers."""
        r = client.get("/api/market/movers", params={"type": "losers", "limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "losers"


class TestSummaryAPI:
    """Test summary API endpoint."""

    def test_summary_returns_data(self, client):
        """GET /api/summary returns summary with date and source."""
        r = client.get("/api/summary")
        assert r.status_code == 200
        data = r.json()
        assert "date" in data
        assert "summary" in data
        assert data["source"] in ("ai", "demo")
        assert len(data["summary"]) > 0


class TestHistoryAccuracyAPI:
    """Projection accuracy endpoint."""

    def test_accuracy_returns_summary(self, client, mock_data_loader):
        """GET /api/history/accuracy returns summary and samples."""
        mock_data_loader.compute_projection_accuracy = MagicMock(
            return_value={
                "summary": {
                    "sampleCount": 1,
                    "meanAbsErrorPct": 3.0,
                    "byRecommendation": {
                        "HOLD": {"count": 1, "meanAbsErrorPct": 3.0},
                    },
                },
                "samples": [
                    {
                        "symbol": "AAPL",
                        "runDate": "2026-01-10",
                        "targetDate": "2026-01-15",
                        "actualDate": "2026-01-15",
                        "predicted": 100.0,
                        "actual": 103.0,
                        "absErrorPct": 3.0,
                        "recommendation": "HOLD",
                    }
                ],
            }
        )
        r = client.get("/api/history/accuracy", params={"days": 30})
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["sampleCount"] == 1
        assert data["summary"]["meanAbsErrorPct"] == 3.0
        assert len(data["samples"]) == 1
        assert data["samples"][0]["symbol"] == "AAPL"


class TestMarketAPIErrors:
    """Test API error handling."""

    def test_summary_404_when_no_data(self, temp_data_dir):
        """Summary returns 404 when no summary files exist."""
        import dashboard.backend.api.market
        mock_loader = MagicMock()
        mock_loader.load_summary.side_effect = ValueError("No summary files found")
        with patch.object(dashboard.backend.api.market, "get_data_loader", return_value=mock_loader):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app
            client = TestClient(app)
            r = client.get("/api/summary")

        assert r.status_code == 404
