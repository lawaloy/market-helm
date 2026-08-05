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


def test_load_from_cache_misses_when_date_missing(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(
        json.dumps({"symbols": ["AAPL", "MSFT"]}),
        encoding="utf-8",
    )
    assert fetcher._load_from_cache("S&P 500") is None


def test_load_from_cache_misses_when_date_invalid(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    cache_file = tmp_path / "SP_500_symbols.json"
    cache_file.write_text(
        json.dumps(
            {
                "date": "not-a-date",
                "symbols": ["AAPL", "MSFT"],
            }
        ),
        encoding="utf-8",
    )
    assert fetcher._load_from_cache("S&P 500") is None


def test_save_to_cache_soft_fails_when_write_raises(tmp_path: Path, monkeypatch) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)

    def boom(*_args, **_kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("builtins.open", boom)
    # Must not raise — corrupt/unwritable cache must not abort fetch paths.
    fetcher._save_to_cache("S&P 500", ["AAPL", "MSFT"])
    assert not (tmp_path / "SP_500_symbols.json").exists()


def test_save_to_cache_preserves_existing_when_serialize_fails(
    tmp_path: Path, monkeypatch
) -> None:
    """A failed rewrite must leave the previous valid cache intact."""
    fetcher = IndexFetcher(cache_dir=tmp_path)
    fetcher._save_to_cache("S&P 500", ["AAPL", "MSFT"])
    cache_file = tmp_path / "SP_500_symbols.json"
    original = cache_file.read_text(encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("disk full during serialize")

    monkeypatch.setattr(json, "dump", boom)
    fetcher._save_to_cache("S&P 500", ["GOOG", "AMZN"])

    assert cache_file.read_text(encoding="utf-8") == original
    assert fetcher._load_from_cache("S&P 500") == ["AAPL", "MSFT"]
    # Temp sibling must not be left behind after a soft-fail.
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_to_cache_replaces_via_temp_sibling(tmp_path: Path) -> None:
    fetcher = IndexFetcher(cache_dir=tmp_path)
    fetcher._save_to_cache("S&P 500", ["AAPL"])
    fetcher._save_to_cache("S&P 500", ["MSFT", "NVDA"])

    assert fetcher._load_from_cache("S&P 500") == ["MSFT", "NVDA"]
    assert list(tmp_path.glob("*.tmp")) == []


def test_init_soft_fails_when_cache_mkdir_raises(tmp_path: Path, monkeypatch) -> None:
    """Unwritable cache roots must not abort IndexFetcher construction."""
    blocked = tmp_path / "blocked-cache"

    def boom(self, *args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", boom)
    fetcher = IndexFetcher(cache_dir=blocked)
    assert fetcher.cache_dir == blocked
    # Construction succeeded; package flag is independent of cache mkdir.
    assert isinstance(fetcher.package_available, bool)
