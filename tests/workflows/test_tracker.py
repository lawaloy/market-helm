"""Tests for MarketHelm tracker workflow."""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def temp_data_dir():
    """Create temp data directory."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_stock_data():
    """Sample stock data for workflow."""
    return [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "close": 150.0,
            "change": 1.5,
            "change_percent": 1.0,
            "volume": 50_000_000,
            "index_name": "S&P 500",
        },
        {
            "symbol": "GOOGL",
            "name": "Alphabet Inc.",
            "close": 140.0,
            "change": -1.4,
            "change_percent": -1.0,
            "volume": 2_000_000,
            "index_name": "NASDAQ-100",
        },
    ]


class TestStockTrackerWorkflow:
    """Test workflow with mocked dependencies."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)
    @patch("src.workflows.tracker.get_indices_to_track", return_value=["S&P 500", "NASDAQ-100"])
    @patch("src.workflows.tracker.StockDataFetcher")
    @patch("src.workflows.tracker.DataStorage")
    @patch("src.workflows.tracker.AlertEngine")
    def test_workflow_run_success(
        self, mock_alert, mock_storage_cls, mock_fetcher_cls, mock_indices, sample_stock_data, temp_data_dir
    ):
        """Workflow completes successfully with mocked fetch and storage."""
        from src.workflows.tracker import StockTrackerWorkflow

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_indices.return_value = {
            "S&P 500": sample_stock_data[:1],
            "NASDAQ-100": sample_stock_data[1:],
        }
        mock_fetcher_cls.return_value = mock_fetcher

        mock_storage = MagicMock()
        mock_storage.save_daily_data.return_value = str(temp_data_dir / "daily_data_2026-01-15.csv")
        mock_storage.save_summary.return_value = str(temp_data_dir / "summary_2026-01-15.json")
        mock_storage.save_projections.return_value = str(temp_data_dir / "projections_2026-01-15.csv")
        mock_storage_cls.return_value = mock_storage

        mock_alert.from_config.return_value = None

        workflow = StockTrackerWorkflow(include_profile=False)
        workflow.fetcher = mock_fetcher
        workflow.storage = mock_storage
        workflow.alert_engine = None
        workflow.ai_summarizer.enabled = False

        result = workflow.run(use_screener=False)

        assert result["success"] is True
        assert len(result["data"]) == 2
        assert "analysis" in result
        assert "projections" in result
        assert "ai_summary" in result
        assert result["ai_summary"] is not None

    @patch("src.workflows.tracker.get_indices_to_track", return_value=["S&P 500"])
    @patch("src.workflows.tracker.StockDataFetcher")
    @patch("src.workflows.tracker.DataStorage")
    @patch("src.workflows.tracker.AlertEngine")
    def test_workflow_handles_fetch_failure(
        self, mock_alert, mock_storage_cls, mock_fetcher_cls, mock_indices
    ):
        """Workflow returns error when fetch fails."""
        from src.workflows.tracker import StockTrackerWorkflow

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_indices.side_effect = Exception("API rate limit exceeded")
        mock_fetcher_cls.return_value = mock_fetcher
        mock_alert.from_config.return_value = None

        workflow = StockTrackerWorkflow(include_profile=False)
        workflow.fetcher = mock_fetcher

        result = workflow.run(use_screener=False)

        assert result["success"] is False
        assert "error" in result

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)
    @patch("src.workflows.tracker.get_indices_to_track", return_value=["S&P 500"])
    @patch("src.workflows.tracker.StockDataFetcher")
    @patch("src.workflows.tracker.DataStorage")
    @patch("src.workflows.tracker.AlertEngine")
    def test_analyze_and_projections_soft_fail(
        self, mock_alert, mock_storage_cls, mock_fetcher_cls, mock_indices, sample_stock_data, temp_data_dir
    ):
        """Analyzer/projector exceptions yield empty dicts so the run can continue."""
        from src.workflows.tracker import StockTrackerWorkflow

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_indices.return_value = {"S&P 500": sample_stock_data}
        mock_fetcher_cls.return_value = mock_fetcher

        mock_storage = MagicMock()
        mock_storage.save_daily_data.return_value = str(
            temp_data_dir / "daily_data_2026-01-15.csv"
        )
        mock_storage.save_summary.return_value = str(
            temp_data_dir / "summary_2026-01-15.json"
        )
        mock_storage.save_projections.return_value = str(
            temp_data_dir / "projections_2026-01-15.csv"
        )
        mock_storage_cls.return_value = mock_storage
        mock_alert.from_config.return_value = None

        workflow = StockTrackerWorkflow(include_profile=False)
        workflow.fetcher = mock_fetcher
        workflow.storage = mock_storage
        workflow.alert_engine = None
        workflow.ai_summarizer.enabled = False
        workflow.analyzer.analyze_daily_data = MagicMock(
            side_effect=RuntimeError("analyzer boom")
        )
        workflow.projector.generate_projections = MagicMock(
            side_effect=RuntimeError("projector boom")
        )

        result = workflow.run(use_screener=False)

        assert result["success"] is True
        assert result["analysis"] == {}
        assert result["projections"] == {}
        mock_storage.save_daily_data.assert_called_once()
        mock_storage.save_summary.assert_called_once()

    @patch("src.alerts.alert_paths.get_enabled_watch_symbols", return_value=["AAPL", "MSFT"])
    @patch("src.workflows.tracker.get_indices_to_track", return_value=["S&P 500"])
    @patch("src.workflows.tracker.StockDataFetcher")
    @patch("src.workflows.tracker.DataStorage")
    @patch("src.workflows.tracker.AlertEngine")
    def test_fetch_data_treats_padded_index_symbols_as_already_present(
        self,
        mock_alert,
        mock_storage_cls,
        mock_fetcher_cls,
        mock_indices,
        mock_watches,
    ):
        """Padded/cased index symbols match normalized watches; skip duplicate fetch."""
        from src.workflows.tracker import StockTrackerWorkflow

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_indices.return_value = {
            "S&P 500": [
                {
                    "symbol": " aapl ",
                    "name": "Apple",
                    "close": 150.0,
                    "volume": 1_000_000,
                    "index_name": "S&P 500",
                },
                {
                    "symbol": float("nan"),
                    "name": "Bad",
                    "close": 1.0,
                    "volume": 1,
                    "index_name": "S&P 500",
                },
            ]
        }
        mock_fetcher.fetch_symbol_data.return_value = {
            "symbol": "MSFT",
            "name": "Microsoft",
            "close": 400.0,
            "volume": 2_000_000,
            "index_name": "WATCH",
        }
        mock_fetcher_cls.return_value = mock_fetcher
        mock_alert.from_config.return_value = None

        workflow = StockTrackerWorkflow(include_profile=False)
        workflow.fetcher = mock_fetcher

        result = workflow._fetch_data(use_screener=False)

        assert result["success"] is True
        symbols = [row["symbol"] for row in result["data"]]
        # Padded AAPL already present → only MSFT fetched once.
        mock_fetcher.fetch_symbol_data.assert_called_once_with("MSFT")
        assert "MSFT" in symbols
        assert any(str(s).strip().upper() == "AAPL" for s in symbols)

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)
    @patch("src.alerts.alert_paths.get_enabled_watch_symbols", return_value=[])
    @patch("src.workflows.tracker.get_indices_to_track", return_value=["S&P 500", "NASDAQ-100"])
    @patch("src.workflows.tracker.StockDataFetcher")
    @patch("src.workflows.tracker.DataStorage")
    @patch("src.workflows.tracker.AlertEngine")
    def test_workflow_top_n_stocks_keeps_highest_volume(
        self,
        mock_alert,
        mock_storage_cls,
        mock_fetcher_cls,
        mock_indices,
        _mock_watches,
        temp_data_dir,
    ):
        """Day-trading top_n must rank by volume across indices."""
        from src.workflows.tracker import StockTrackerWorkflow

        stocks = [
            {"symbol": "LOW", "close": 10.0, "volume": 100, "change_percent": 0.1, "index_name": "S&P 500"},
            {"symbol": "MID", "close": 20.0, "volume": 5_000, "change_percent": 0.2, "index_name": "S&P 500"},
            {"symbol": "HIGH", "close": 30.0, "volume": 50_000, "change_percent": 0.3, "index_name": "NASDAQ-100"},
            {"symbol": "TOP", "close": 40.0, "volume": 90_000, "change_percent": 0.4, "index_name": "NASDAQ-100"},
        ]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_indices.return_value = {
            "S&P 500": stocks[:2],
            "NASDAQ-100": stocks[2:],
        }
        mock_fetcher_cls.return_value = mock_fetcher

        mock_storage = MagicMock()
        mock_storage.save_daily_data.return_value = str(temp_data_dir / "daily.csv")
        mock_storage.save_summary.return_value = str(temp_data_dir / "summary.json")
        mock_storage.save_projections.return_value = str(temp_data_dir / "proj.csv")
        mock_storage_cls.return_value = mock_storage
        mock_alert.from_config.return_value = None

        workflow = StockTrackerWorkflow(include_profile=False)
        workflow.fetcher = mock_fetcher
        workflow.storage = mock_storage
        workflow.alert_engine = None
        workflow.ai_summarizer.enabled = False

        result = workflow.run(use_screener=False, top_n_stocks=2)

        assert result["success"] is True
        kept = [row["symbol"] for row in result["data"]]
        assert kept == ["TOP", "HIGH"]
        mock_fetcher.fetch_all_indices.assert_called_once()
        kwargs = mock_fetcher.fetch_all_indices.call_args.kwargs
        assert kwargs["max_symbols_per_index"] == 1
