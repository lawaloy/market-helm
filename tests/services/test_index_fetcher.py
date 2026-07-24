"""Tests for index symbol caching, routing, and fallback behavior."""

from datetime import datetime, timedelta
import json
from unittest.mock import MagicMock

from src.services.index_fetcher import IndexFetcher


def test_get_index_symbols_routes_aliases_and_unknown(tmp_path, monkeypatch):
    fetcher = IndexFetcher(cache_dir=str(tmp_path))
    monkeypatch.setattr(fetcher, "get_sp500_symbols", lambda: ["AAPL"])
    monkeypatch.setattr(fetcher, "get_nasdaq100_symbols", lambda: ["MSFT"])
    monkeypatch.setattr(fetcher, "get_dow30_symbols", lambda: ["IBM"])

    assert fetcher.get_index_symbols("SP500") == ["AAPL"]
    assert fetcher.get_index_symbols("nasdaq 100") == ["MSFT"]
    assert fetcher.get_index_symbols("DJIA") == ["IBM"]
    assert fetcher.get_index_symbols("Russell 2000") == []


def test_load_from_cache_returns_fresh_symbols_and_ignores_stale(tmp_path):
    fetcher = IndexFetcher(cache_dir=str(tmp_path))
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(
        json.dumps(
            {
                "date": datetime.now().isoformat(),
                "symbols": ["AAPL", "MSFT"],
            }
        )
    )

    assert fetcher._load_from_cache("S&P 500") == ["AAPL", "MSFT"]

    cache_file.write_text(
        json.dumps(
            {
                "date": (datetime.now() - timedelta(days=8)).isoformat(),
                "symbols": ["OLD"],
            }
        )
    )
    assert fetcher._load_from_cache("S&P 500") is None


def test_get_sp500_symbols_uses_cache_before_package(tmp_path, monkeypatch):
    fetcher = IndexFetcher(cache_dir=str(tmp_path))
    package = MagicMock()
    fetcher.package_available = True
    fetcher.ticker_symbols = package
    monkeypatch.setattr(fetcher, "_load_from_cache", lambda _name: ["CACHED"])

    assert fetcher.get_sp500_symbols() == ["CACHED"]
    package.get_stocks_by_index.assert_not_called()


def test_get_sp500_symbols_falls_back_when_package_unavailable(tmp_path):
    """Package/cache misses must return the static fallback, not crash."""
    fetcher = IndexFetcher(cache_dir=str(tmp_path))
    fetcher.package_available = False
    fetcher.ticker_symbols = None

    symbols = fetcher.get_sp500_symbols()

    assert symbols == fetcher._get_minimal_fallback("S&P 500")
    assert "AAPL" in symbols


def test_get_sp500_symbols_falls_back_when_package_returns_too_few(tmp_path):
    fetcher = IndexFetcher(cache_dir=str(tmp_path))
    package = MagicMock()
    package.get_stocks_by_index.return_value = [{"symbol": "AAPL"}]
    fetcher.package_available = True
    fetcher.ticker_symbols = package

    symbols = fetcher.get_sp500_symbols()

    assert symbols == fetcher._get_minimal_fallback("S&P 500")
    assert not (tmp_path / "SP_500_symbols.json").exists()


def test_get_sp500_symbols_caches_valid_package_result(tmp_path):
    fetcher = IndexFetcher(cache_dir=str(tmp_path))
    package = MagicMock()
    package.get_stocks_by_index.return_value = [
        {"symbol": f"S{i}"} for i in range(401)
    ]
    fetcher.package_available = True
    fetcher.ticker_symbols = package

    symbols = fetcher.get_sp500_symbols()

    assert len(symbols) == 401
    cached = json.loads((tmp_path / "SP_500_symbols.json").read_text())
    assert cached["symbols"] == symbols
