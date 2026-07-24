"""Index cache must miss on wrong-type symbols instead of iterating a string."""

import json
from datetime import datetime
from pathlib import Path

from src.services.index_fetcher import IndexFetcher


def test_load_from_cache_misses_when_symbols_is_string(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(
        json.dumps(
            {
                "date": datetime.now().isoformat(),
                "symbols": "AAPL",
            }
        ),
        encoding="utf-8",
    )
    assert fetcher._load_from_cache("S&P 500") is None


def test_load_from_cache_misses_when_symbols_is_object(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(
        json.dumps(
            {
                "date": datetime.now().isoformat(),
                "symbols": {"ticker": "AAPL"},
            }
        ),
        encoding="utf-8",
    )
    assert fetcher._load_from_cache("S&P 500") is None


def test_load_from_cache_misses_when_root_is_list(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(json.dumps(["AAPL"]), encoding="utf-8")
    assert fetcher._load_from_cache("S&P 500") is None


def test_load_from_cache_still_accepts_list_symbols(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(
        json.dumps(
            {
                "date": datetime.now().isoformat(),
                "symbols": ["AAPL", "MSFT"],
            }
        ),
        encoding="utf-8",
    )
    assert fetcher._load_from_cache("S&P 500") == ["AAPL", "MSFT"]
