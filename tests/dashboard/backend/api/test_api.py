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
            assert "MarketHelm" in data["service"]
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

    def test_market_overview_strips_spaces_from_index_keys(self, client):
        """Index keys drop spaces only so 'S&P 500' becomes 'S&P500'."""
        r = client.get("/api/market/overview")
        assert r.status_code == 200
        indices = r.json()["indices"]
        assert set(indices) == {"S&P500", "NASDAQ-100"}
        assert indices["S&P500"]["stocks"] == 2
        assert indices["S&P500"]["gainers"] == 2
        assert indices["S&P500"]["losers"] == 0
        assert indices["NASDAQ-100"]["stocks"] == 1
        assert indices["NASDAQ-100"]["losers"] == 1

    def test_market_movers_gainers(self, client):
        """GET /api/market/movers?type=gainers returns top gainers."""
        r = client.get("/api/market/movers", params={"type": "gainers", "limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "gainers"
        assert len(data["data"]) >= 1
        assert all(row["changePercent"] > 0 for row in data["data"])
        percents = [row["changePercent"] for row in data["data"]]
        assert percents == sorted(percents, reverse=True)

    def test_market_movers_losers(self, client):
        """GET /api/market/movers?type=losers returns top losers."""
        r = client.get("/api/market/movers", params={"type": "losers", "limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "losers"
        assert len(data["data"]) == 1
        assert all(row["changePercent"] < 0 for row in data["data"])
        assert data["data"][0]["symbol"] == "GOOGL"

    def test_market_movers_do_not_backfill_opposite_sign(self, client):
        """Large limit must not mix gainers into losers (or vice versa)."""
        losers = client.get("/api/market/movers", params={"type": "losers", "limit": 50})
        assert losers.status_code == 200
        loser_rows = losers.json()["data"]
        assert len(loser_rows) == 1
        assert all(row["changePercent"] < 0 for row in loser_rows)

        gainers = client.get("/api/market/movers", params={"type": "gainers", "limit": 50})
        assert gainers.status_code == 200
        gainer_rows = gainers.json()["data"]
        assert len(gainer_rows) == 2
        assert all(row["changePercent"] > 0 for row in gainer_rows)
        assert [row["symbol"] for row in gainer_rows] == ["AAPL", "MSFT"]

    def test_market_overview_404_when_no_latest_date(self, temp_data_dir):
        """No latest date must stay 404 (not swallowed into 500)."""
        import dashboard.backend.api.market

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = None
        with patch.object(
            dashboard.backend.api.market, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/market/overview")

        assert r.status_code == 404
        assert "No data available" in r.json()["detail"]

    def test_market_overview_404_when_daily_empty(self, temp_data_dir):
        """Empty daily frame is treated as no usable overview data."""
        import dashboard.backend.api.market

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = "2026-01-15"
        mock_loader.load_daily_data.return_value = pd.DataFrame(
            {"change_percent": pd.Series(dtype=float)}
        )
        with patch.object(
            dashboard.backend.api.market, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/market/overview")

        assert r.status_code == 404

    def test_market_overview_404_when_change_percent_missing(self, temp_data_dir):
        """Missing change_percent column must 404 instead of KeyError→500."""
        import dashboard.backend.api.market

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = "2026-01-15"
        mock_loader.load_daily_data.return_value = pd.DataFrame({"symbol": ["AAPL"]})
        with patch.object(
            dashboard.backend.api.market, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/market/overview")

        assert r.status_code == 404

    def test_market_overview_coerces_all_nan_change_percent(self, temp_data_dir):
        """All-NaN change_percent must yield finite 0.0 stats, not null JSON floats."""
        import dashboard.backend.api.market

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = "2026-01-15"
        mock_loader.load_daily_data.return_value = pd.DataFrame(
            {
                "symbol": ["AAPL", "MSFT"],
                "change_percent": [float("nan"), float("nan")],
                "index_name": ["S&P 500", "S&P 500"],
            }
        )
        with patch.object(
            dashboard.backend.api.market, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/market/overview")

        assert r.status_code == 200
        data = r.json()
        assert data["totalStocks"] == 2
        assert data["averageChange"] == 0.0
        assert data["maxChange"] == 0.0
        assert data["minChange"] == 0.0
        assert data["indices"]["S&P500"]["avgChange"] == 0.0


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

    def test_summary_uses_ai_when_non_blank(self, client, temp_data_dir, sample_summary):
        """Whitespace-only AI text falls back to demo; real AI text is preferred."""
        path = temp_data_dir / "summary_2026-01-15.json"
        with open(path) as f:
            payload = json.load(f)

        payload["ai_summary"] = "   "
        with open(path, "w") as f:
            json.dump(payload, f)
        blank = client.get("/api/summary").json()
        assert blank["source"] == "demo"
        assert "gainers" in blank["summary"]

        payload["ai_summary"] = "  Markets advanced on strong tech leadership.  "
        with open(path, "w") as f:
            json.dump(payload, f)
        ai = client.get("/api/summary").json()
        assert ai["source"] == "ai"
        assert ai["summary"] == "Markets advanced on strong tech leadership."

    def test_summary_demo_tolerates_partial_legacy_fields(
        self, client, temp_data_dir, sample_summary
    ):
        """Partial/legacy summary JSON must soft-fail to a demo string, not 500."""
        path = temp_data_dir / "summary_2026-01-15.json"
        with open(path) as f:
            payload = json.load(f)

        payload.pop("ai_summary", None)
        payload["analysis"] = {
            "summary": {
                "gainers": "2",
                "losers": None,
                "average_change_percent": "not-a-number",
            },
            "top_gainers": [{"symbol": "AAPL"}],  # missing change_percent
            "top_losers": [{"change_percent": -1.5}],  # missing symbol
        }
        payload["exchange_comparison"] = {
            "NYSE": {"average_change_percent": None},
            "NASDAQ": "legacy-non-dict",
        }
        with open(path, "w") as f:
            json.dump(payload, f)

        r = client.get("/api/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "demo"
        assert "sentiment" in data["summary"]
        assert "AAPL led" not in data["summary"]
        assert "declined" not in data["summary"]


@pytest.fixture
def sample_projections(temp_data_dir, sample_daily_data):
    """Create sample projections CSV aligned with daily fixtures."""
    df = pd.DataFrame(
        {
            "symbol": ["AAPL", "GOOGL", "MSFT", "ORPHAN"],
            "name": ["Apple", "Alphabet", "Microsoft", "Orphan Co"],
            "target_mid": [160.0, 2700.0, 360.0, 50.0],
            "expected_change_percent": [2.5, -1.5, 0.2, 3.0],
            "confidence": [80, 70, 60, 90],
            "recommendation": ["STRONG BUY", "SELL", "HOLD", "STRONG BUY"],
            "risk_level": ["Low", "High", "Medium", "Medium"],
            "trend": ["Bullish", "Bearish", "Neutral", "Bullish"],
            "reason": ["momentum", "weakness", "range", "breakout"],
            "momentum_score": [1.2, -0.8, 0.1, 1.5],
            "volatility_score": [0.4, 0.9, 0.3, 0.5],
        }
    )
    path = temp_data_dir / "projections_2026-01-15.csv"
    df.to_csv(path, index=False)
    return path


class TestStocksAPI:
    """Stock detail and historical endpoints."""

    def test_stock_detail_uppercases_symbol_and_includes_projection(
        self, client, sample_projections
    ):
        r = client.get("/api/stocks/aapl")
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple"
        assert data["currentData"]["price"] == 150.0
        assert data["projection"]["recommendation"] == "STRONG BUY"
        assert data["projection"]["targetPrice"] == 160.0
        assert data["technical"]["momentum"] == 1.2

    def test_stock_detail_404_for_unknown_symbol(self, client):
        r = client.get("/api/stocks/ZZZZ")
        assert r.status_code == 404
        assert r.json()["detail"] == "Stock not found."

    def test_stock_detail_404_when_price_fields_missing(self, temp_data_dir):
        """Missing close/change/change_percent must 404 instead of KeyError→500."""
        import dashboard.backend.api.stocks

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = "2026-01-15"
        mock_loader.load_daily_data.return_value = pd.DataFrame(
            {"symbol": ["AAPL"], "name": ["Apple"]}
        )
        with patch.object(
            dashboard.backend.api.stocks, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/stocks/AAPL")

        assert r.status_code == 404
        assert r.json()["detail"] == "Stock not found."

    def test_stock_detail_404_when_price_is_nan(self, temp_data_dir):
        """Non-finite close/change/change_percent must 404 (not null JSON numbers)."""
        import dashboard.backend.api.stocks

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = "2026-01-15"
        mock_loader.load_daily_data.return_value = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "close": [float("nan")],
                "change": [1.0],
                "change_percent": [0.5],
                "volume": [1_000],
            }
        )
        with patch.object(
            dashboard.backend.api.stocks, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/stocks/AAPL")

        assert r.status_code == 404
        assert r.json()["detail"] == "Stock not found."

    def test_stock_detail_omits_projection_when_target_is_nan(
        self, client, mock_data_loader, temp_data_dir
    ):
        """Finite daily prices with NaN projection fields soft-fail projection to null."""
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "target_mid": [float("nan")],
                "expected_change_percent": [2.5],
                "confidence": [80],
                "recommendation": ["BUY"],
                "risk_level": ["Low"],
                "trend": ["Bullish"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)

        r = client.get("/api/stocks/AAPL")
        assert r.status_code == 200
        data = r.json()
        assert data["currentData"]["price"] == 150.0
        assert data["projection"] is None
        assert data["technical"] is None

    def test_stock_historical_skips_nan_days(self, client, mock_data_loader, temp_data_dir):
        """One corrupt day is omitted; valid siblings still return 200."""
        from datetime import datetime, timedelta

        recent = datetime.now().strftime("%Y-%m-%d")
        prior = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "close": [float("nan")],
                "change": [0.0],
                "change_percent": [float("nan")],
                "volume": [1],
            }
        ).to_csv(temp_data_dir / f"daily_data_{recent}.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "close": [150.0],
                "change": [1.0],
                "change_percent": [0.7],
                "volume": [2_000],
            }
        ).to_csv(temp_data_dir / f"daily_data_{prior}.csv", index=False)

        r = client.get("/api/stocks/AAPL/historical", params={"days": 7})
        assert r.status_code == 200
        data = r.json()
        assert [point["date"] for point in data["data"]] == [prior]
        assert data["data"][0]["close"] == 150.0

    def test_stock_historical_404_when_all_points_invalid(
        self, client, mock_data_loader, temp_data_dir
    ):
        """If every day is non-finite, historical returns 404 like an empty series."""
        from datetime import datetime

        recent = datetime.now().strftime("%Y-%m-%d")
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "close": [float("nan")],
                "change": [0.0],
                "change_percent": [float("inf")],
                "volume": [1],
            }
        ).to_csv(temp_data_dir / f"daily_data_{recent}.csv", index=False)

        r = client.get("/api/stocks/AAPL/historical", params={"days": 7})
        assert r.status_code == 404
        assert r.json()["detail"] == "No historical data found."

    def test_stock_historical_returns_points(self, client, mock_data_loader, temp_data_dir):
        from datetime import datetime, timedelta

        recent = datetime.now().strftime("%Y-%m-%d")
        older = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "close": [155.0],
                "change": [5.0],
                "change_percent": [3.3],
                "volume": [40_000_000],
            }
        ).to_csv(temp_data_dir / f"daily_data_{recent}.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "target_mid": [165.0],
                "expected_change_percent": [2.0],
                "confidence": [75],
                "recommendation": ["BUY"],
            }
        ).to_csv(temp_data_dir / f"projections_{recent}.csv", index=False)
        # Stale file outside the requested window should be ignored.
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "name": ["Apple"],
                "close": [100.0],
                "change": [0.0],
                "change_percent": [0.0],
                "volume": [1],
            }
        ).to_csv(temp_data_dir / f"daily_data_{older}.csv", index=False)

        r = client.get("/api/stocks/AAPL/historical", params={"days": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert [point["date"] for point in data["data"]] == [recent]
        point = data["data"][0]
        assert point["close"] == 155.0
        assert point["projection"]["targetPrice"] == 165.0
        assert point["projection"]["recommendation"] == "BUY"

    def test_stock_detail_matches_padded_daily_and_projection_symbols(
        self, client, mock_data_loader, temp_data_dir
    ):
        """Padded CSV symbols must still resolve via normalize_ticker matching."""
        pd.DataFrame(
            {
                "symbol": [" AAPL "],
                "name": ["Apple"],
                "close": [151.0],
                "change": [1.0],
                "change_percent": [0.7],
                "volume": [1_000],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
        pd.DataFrame(
            {
                "symbol": [" aapl "],
                "name": ["Apple"],
                "target_mid": [160.0],
                "expected_change_percent": [2.0],
                "confidence": [80],
                "recommendation": ["BUY"],
                "risk_level": ["Low"],
                "trend": ["Bullish"],
                "momentum_score": [1.1],
                "volatility_score": [0.4],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)

        r = client.get("/api/stocks/aapl")
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert data["currentData"]["price"] == 151.0
        assert data["projection"]["targetPrice"] == 160.0
        assert data["projection"]["recommendation"] == "BUY"

    def test_stock_historical_matches_padded_csv_symbols(
        self, client, mock_data_loader, temp_data_dir
    ):
        """Historical series must find padded daily/projection rows for the path symbol."""
        from datetime import date, timedelta

        recent = (date.today() - timedelta(days=1)).isoformat()
        pd.DataFrame(
            {
                "symbol": [" AAPL "],
                "name": ["Apple"],
                "close": [155.0],
                "change": [1.0],
                "change_percent": [0.5],
                "volume": [2_000],
            }
        ).to_csv(temp_data_dir / f"daily_data_{recent}.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["aapl"],
                "target_mid": [165.0],
                "confidence": [70],
                "recommendation": ["BUY"],
                "expected_change_percent": [3.0],
            }
        ).to_csv(temp_data_dir / f"projections_{recent}.csv", index=False)

        r = client.get("/api/stocks/AAPL/historical", params={"days": 7})
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert len(data["data"]) >= 1
        by_date = {point["date"]: point for point in data["data"]}
        assert by_date[recent]["close"] == 155.0
        assert by_date[recent]["projection"]["targetPrice"] == 165.0


class TestProjectionsAPI:
    """Projections summary and opportunities endpoints."""

    def test_projections_summary_maps_recommendations_and_sentiment(
        self, client, sample_projections
    ):
        r = client.get("/api/projections/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["date"] == "2026-01-15"
        assert data["targetDate"] == "2026-01-20"
        assert data["totalProjections"] == 4
        assert data["sentiment"] == "Bullish"
        assert data["recommendations"]["STRONG_BUY"] == 2
        assert data["recommendations"]["SELL"] == 1
        assert data["recommendations"]["HOLD"] == 1
        assert data["trends"]["Bullish"] == 2
        assert data["riskProfile"]["Medium"] == 2

    def test_opportunities_filters_and_defaults_missing_daily_price(
        self, client, sample_projections
    ):
        r = client.get(
            "/api/projections/opportunities",
            params={"type": "STRONG_BUY", "limit": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "STRONG_BUY"
        assert data["count"] == 2
        symbols = [row["symbol"] for row in data["opportunities"]]
        assert symbols == ["ORPHAN", "AAPL"]
        by_symbol = {row["symbol"]: row for row in data["opportunities"]}
        assert by_symbol["AAPL"]["currentPrice"] == 150.0
        assert by_symbol["ORPHAN"]["currentPrice"] == 0
        assert by_symbol["ORPHAN"]["volume"] == 0


class TestStocksAPIEdges:
    """Stock detail/historical error and soft-fail paths."""

    def test_stock_detail_404_when_no_latest_date(self, temp_data_dir):
        import dashboard.backend.api.stocks

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = None
        with patch.object(
            dashboard.backend.api.stocks, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/stocks/AAPL")

        assert r.status_code == 404
        assert r.json()["detail"] == "No data available"

    def test_stock_detail_survives_projection_load_failure(
        self, client, mock_data_loader
    ):
        mock_data_loader.load_projections = MagicMock(
            side_effect=FileNotFoundError("projections missing")
        )
        r = client.get("/api/stocks/AAPL")
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert data["currentData"]["price"] == 150.0
        assert data["projection"] is None
        assert data["technical"] is None

    def test_stock_historical_404_when_empty(self, client, mock_data_loader):
        mock_data_loader.load_historical_data = MagicMock(return_value=[])
        r = client.get("/api/stocks/AAPL/historical", params={"days": 7})
        assert r.status_code == 404
        assert r.json()["detail"] == "No historical data found."


class TestProjectionsSentimentBands:
    """Projections summary sentiment thresholds (±1.0)."""

    def _write_projections(self, temp_data_dir, changes):
        df = pd.DataFrame(
            {
                "symbol": [f"S{i}" for i in range(len(changes))],
                "name": [f"Stock {i}" for i in range(len(changes))],
                "target_mid": [100.0] * len(changes),
                "expected_change_percent": changes,
                "confidence": [50] * len(changes),
                "recommendation": ["HOLD"] * len(changes),
                "risk_level": ["Medium"] * len(changes),
                "trend": ["Neutral"] * len(changes),
            }
        )
        path = temp_data_dir / "projections_2026-01-15.csv"
        df.to_csv(path, index=False)
        return path

    def test_sentiment_neutral_and_bearish_bands(self, client, temp_data_dir):
        self._write_projections(temp_data_dir, [0.5, -0.5])
        neutral = client.get("/api/projections/summary").json()
        assert neutral["sentiment"] == "Neutral"
        assert neutral["expectedMarketMove"] == 0.0

        self._write_projections(temp_data_dir, [-2.0, -1.5])
        bearish = client.get("/api/projections/summary").json()
        assert bearish["sentiment"] == "Bearish"
        assert bearish["expectedMarketMove"] == -1.75

    def test_projections_summary_404_when_no_date(self, temp_data_dir):
        import dashboard.backend.api.projections

        mock_loader = MagicMock()
        mock_loader.get_latest_date.return_value = None
        with patch.object(
            dashboard.backend.api.projections, "get_data_loader", return_value=mock_loader
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/projections/summary")

        assert r.status_code == 404
        assert r.json()["detail"] == "No data available"


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

    def test_accuracy_valueerror_maps_to_404(self, client, mock_data_loader):
        """GET /api/history/accuracy maps loader ValueError to 404 (not 500)."""
        mock_data_loader.compute_projection_accuracy = MagicMock(
            side_effect=ValueError("No projection files found")
        )
        r = client.get("/api/history/accuracy", params={"days": 30})
        assert r.status_code == 404
        assert r.json()["detail"] == "No data available."

    def test_history_dates_and_symbols_valueerror_maps_to_404(self, client, mock_data_loader):
        """GET /api/history/dates and /symbols map loader ValueError to 404."""
        mock_data_loader.get_available_dates = MagicMock(
            side_effect=ValueError("Data directory not found")
        )
        dates = client.get("/api/history/dates")
        assert dates.status_code == 404
        assert dates.json()["detail"] == "No data available."

        mock_data_loader.get_latest_date = MagicMock(
            side_effect=ValueError("No projection files found")
        )
        symbols = client.get("/api/history/symbols")
        assert symbols.status_code == 404
        assert symbols.json()["detail"] == "No data available."


class TestMarketAPIErrors:
    """Test API error handling."""

    def test_data_info_404_when_data_dir_missing(self):
        """GET /api/data-info returns 404 when DATA_DIR/user data path does not exist (not 500)."""
        with patch(
            "dashboard.backend.services.data_loader.get_data_loader",
            side_effect=ValueError("Data directory not found: /nonexistent"),
        ):
            from fastapi.testclient import TestClient
            from dashboard.backend.main import app

            client = TestClient(app)
            r = client.get("/api/data-info")

        assert r.status_code == 404
        assert r.json()["detail"] == "No data available."

    def test_data_info_happy_path(self, client, mock_data_loader, temp_data_dir):
        """GET /api/data-info reports latest date, trading-day target, and needs_fetch."""
        with patch(
            "dashboard.backend.services.data_loader.get_data_loader",
            return_value=mock_data_loader,
        ):
            with patch(
                "dashboard.backend.services.data_loader.get_most_recent_trading_day",
                return_value="2026-01-16",
            ):
                r = client.get("/api/data-info")

        assert r.status_code == 200
        data = r.json()
        assert data["data_dir"] == str(temp_data_dir)
        assert data["latest_date"] == "2026-01-15"
        assert data["target_trading_day"] == "2026-01-16"
        assert data["needs_fetch"] is True
        assert "2026-01-15" in data["available_dates"]

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

    def test_summary_404_when_json_corrupt(self, client, mock_data_loader, temp_data_dir):
        """Corrupt summary JSON must 404 via ValueError mapping, not generic 500."""
        path = temp_data_dir / "summary_2026-01-15.json"
        path.write_text("{not-valid-json", encoding="utf-8")

        r = client.get("/api/summary")
        assert r.status_code == 404
        assert r.json()["detail"] == "No data available."


class TestHistorySummaryAPI:
    """Historical projections summary endpoint."""

    def test_history_summary_coerces_all_nan_means(
        self, client, mock_data_loader, temp_data_dir
    ):
        """All-NaN confidence/expected means must serialize as finite 0.0 + Neutral."""
        pd.DataFrame(
            {
                "symbol": ["AAPL", "MSFT"],
                "name": ["Apple", "Microsoft"],
                "target_mid": [160.0, 360.0],
                "expected_change_percent": [float("nan"), float("nan")],
                "confidence": [float("nan"), float("nan")],
                "recommendation": ["HOLD", "HOLD"],
                "risk_level": ["Medium", "Medium"],
                "trend": ["Neutral", "Neutral"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)

        r = client.get("/api/history/summary", params={"days": 7})
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 1
        point = data["data"][0]
        assert point["averageConfidence"] == 0.0
        assert point["expectedMarketMove"] == 0.0
        assert point["sentiment"] == "Neutral"
