"""Tests for durable market_bars storage and CSV dual-write."""

from datetime import date

import pytest

from src.storage.database import LATEST_SCHEMA_VERSION, get_connection, init_database
from src.storage.data_storage import DataStorage
from src.storage.market_bars import (
    default_sidecar_path,
    dual_write_market_bars,
    list_market_bar_dates,
    load_market_bars,
    upsert_market_bars,
)


@pytest.fixture
def app_db(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_migration_six_creates_market_bars(app_db):
    assert LATEST_SCHEMA_VERSION == 6
    with get_connection() as conn:
        row = conn.execute(
            "SELECT name FROM schema_migrations WHERE version = 6"
        ).fetchone()
        assert row["name"] == "market_bars"
        cols = {
            item["name"]
            for item in conn.execute("PRAGMA table_info(market_bars)").fetchall()
        }
    assert "trade_date" in cols
    assert "close" in cols


def test_upsert_and_load_via_app_database(app_db):
    written = upsert_market_bars(
        [
            {"symbol": "AAPL", "name": "Apple", "close": 150.5, "volume": 1_000},
            {"symbol": "msft", "close": 400.0},
            {"symbol": "BAD", "close": float("nan")},
        ],
        date(2026, 9, 18),
    )
    assert written == 2
    rows = load_market_bars("2026-09-18")
    assert [row["symbol"] for row in rows] == ["AAPL", "MSFT"]
    assert rows[0]["close"] == 150.5
    assert list_market_bar_dates() == ["2026-09-18"]


def test_upsert_replaces_same_trade_date_symbol(app_db):
    upsert_market_bars([{"symbol": "AAPL", "close": 10.0}], "2026-09-18")
    upsert_market_bars([{"symbol": "AAPL", "close": 11.0}], "2026-09-18")
    rows = load_market_bars("2026-09-18")
    assert len(rows) == 1
    assert rows[0]["close"] == 11.0


def test_sidecar_sqlite_when_database_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    written = upsert_market_bars(
        [{"symbol": "AAPL", "close": 12.0}],
        "2026-09-18",
        data_dir=data_dir,
    )
    assert written == 1
    assert default_sidecar_path(data_dir).is_file()
    rows = load_market_bars("2026-09-18", data_dir=data_dir)
    assert rows[0]["close"] == 12.0


def test_dual_write_swallows_errors(monkeypatch, tmp_path):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)

    def boom(*_args, **_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("src.storage.market_bars.upsert_market_bars", boom)
    assert dual_write_market_bars([{"symbol": "AAPL", "close": 1}], "2026-09-18") == 0


def test_save_daily_data_dual_writes_to_sidecar(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    data_dir = tmp_path / "data"
    storage = DataStorage(data_dir=str(data_dir))
    path = storage.save_daily_data(
        [{"symbol": "AAPL", "name": "Apple", "close": 99.0, "volume": 10}],
        date=date(2026, 9, 18),
    )
    assert path.endswith("daily_data_2026-09-18.csv")
    assert (data_dir / "daily_data_2026-09-18.csv").is_file()
    rows = load_market_bars("2026-09-18", data_dir=data_dir)
    assert len(rows) == 1
    assert rows[0]["close"] == 99.0
