"""Close-history loader for RSI alert evaluation."""

from unittest.mock import MagicMock, patch

from src.alerts.price_history import (
    closes_by_symbol,
    closes_from_candle_payload,
    load_symbol_closes,
    load_symbol_closes_from_csv,
    load_symbol_closes_from_market_bars,
    merge_latest_close,
)
from src.storage.database import init_database
from src.storage.market_bars import upsert_market_bars
from tests.helpers.market_bars import seed_daily_bars


def test_load_symbol_closes_from_daily_csvs(tmp_path):
    for day, close in [
        ("2026-09-01", 100.0),
        ("2026-09-02", 101.5),
        ("2026-09-03", 99.0),
    ]:
        path = tmp_path / f"daily_data_{day}.csv"
        path.write_text(
            "symbol,close,volume\nAAPL,{close},1000\nMSFT,200,1000\n".format(close=close),
            encoding="utf-8",
        )

    assert load_symbol_closes_from_csv("AAPL", data_dir=tmp_path) == [100.0, 101.5, 99.0]
    assert load_symbol_closes_from_csv("msft", data_dir=tmp_path) == [200.0, 200.0, 200.0]
    assert load_symbol_closes_from_csv("ZZZ", data_dir=tmp_path) == []


def test_merge_latest_close_replaces_last_bar():
    assert merge_latest_close([10.0, 11.0], 12.0) == [10.0, 12.0]
    assert merge_latest_close([10.0, 11.0], 11.0) == [10.0, 11.0]
    assert merge_latest_close([], 9.5) == [9.5]


def test_merge_latest_close_ignores_non_finite_latest():
    series = [10.0, 11.0]
    assert merge_latest_close(series, float("nan")) == series
    assert merge_latest_close(series, float("inf")) == series
    assert merge_latest_close(series, "nope") == series
    assert merge_latest_close(series, None) == series


def test_closes_from_candle_payload_sorts_by_timestamp():
    payload = {
        "s": "ok",
        "t": [300, 100, 200],
        "c": [30.0, 10.0, 20.0],
    }
    assert closes_from_candle_payload(payload) == [10.0, 20.0, 30.0]
    assert closes_from_candle_payload({"s": "no_data", "c": [1.0]}) == []


def test_load_symbol_closes_prefers_provider_over_csv(tmp_path):
    path = tmp_path / "daily_data_2026-09-01.csv"
    path.write_text("symbol,close\nAAPL,1.0\n", encoding="utf-8")

    client = MagicMock()
    client.get_candle_data.return_value = {
        "s": "ok",
        "t": list(range(20)),
        "c": [float(i) for i in range(20)],
    }

    closes = load_symbol_closes("AAPL", data_dir=tmp_path, client=client)
    assert closes == [float(i) for i in range(20)]
    client.get_candle_data.assert_called_once()


def test_load_symbol_closes_falls_back_to_csv_when_provider_empty(tmp_path):
    for day, close in [("2026-09-01", 100.0), ("2026-09-02", 101.0)]:
        (tmp_path / f"daily_data_{day}.csv").write_text(
            f"symbol,close\nAAPL,{close}\n",
            encoding="utf-8",
        )
    client = MagicMock()
    client.get_candle_data.side_effect = RuntimeError("no key")

    closes = load_symbol_closes("AAPL", data_dir=tmp_path, client=client)
    assert closes == [100.0, 101.0]


def test_load_symbol_closes_from_market_bars_sidecar(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    seed_daily_bars(tmp_path, "2026-09-01", [{"symbol": "AAPL", "close": 100.0}])
    seed_daily_bars(tmp_path, "2026-09-02", [{"symbol": "AAPL", "close": 101.5}])
    seed_daily_bars(tmp_path, "2026-09-03", [{"symbol": "AAPL", "close": 99.0}])

    assert load_symbol_closes_from_market_bars("AAPL", data_dir=tmp_path) == [
        100.0,
        101.5,
        99.0,
    ]
    assert load_symbol_closes_from_market_bars("msft", data_dir=tmp_path) == []


def test_load_symbol_closes_uses_market_bars_when_csv_gone(tmp_path, monkeypatch):
    """Post-#635: no daily_data CSV is written; RSI must still see saved bars."""
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    seed_daily_bars(tmp_path, "2026-09-01", [{"symbol": "AAPL", "close": 100.0}])
    seed_daily_bars(tmp_path, "2026-09-02", [{"symbol": "AAPL", "close": 101.0}])
    client = MagicMock()
    client.get_candle_data.side_effect = RuntimeError("rate limited")

    closes = load_symbol_closes("AAPL", data_dir=tmp_path, client=client)
    assert closes == [100.0, 101.0]
    assert list(tmp_path.glob("daily_data_*.csv")) == []


def test_load_symbol_closes_prefers_market_bars_over_stale_csv(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    (tmp_path / "daily_data_2026-09-01.csv").write_text(
        "symbol,close\nAAPL,1.0\n",
        encoding="utf-8",
    )
    seed_daily_bars(tmp_path, "2026-09-01", [{"symbol": "AAPL", "close": 150.0}])
    seed_daily_bars(tmp_path, "2026-09-02", [{"symbol": "AAPL", "close": 151.0}])
    client = MagicMock()
    client.get_candle_data.return_value = {"s": "no_data"}

    closes = load_symbol_closes("AAPL", data_dir=tmp_path, client=client)
    assert closes == [150.0, 151.0]


def test_load_symbol_closes_from_hosted_market_bars(tmp_path, monkeypatch):
    db_path = tmp_path / "hosted.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    upsert_market_bars(
        [{"symbol": "AAPL", "close": 200.0}],
        "2026-09-10",
        source="test",
    )
    upsert_market_bars(
        [{"symbol": "AAPL", "close": 202.0}],
        "2026-09-11",
        source="test",
    )
    client = MagicMock()
    client.get_candle_data.side_effect = RuntimeError("no key")

    # data_dir is ignored in hosted mode; bars come from the app database.
    closes = load_symbol_closes("AAPL", data_dir=tmp_path / "unused", client=client)
    assert closes == [200.0, 202.0]


def test_load_symbol_closes_prefers_local_when_provider_is_partial(tmp_path, monkeypatch):
    """Short Finnhub series must not beat a longer durable market_bars history."""
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    local = [100.0 + i for i in range(12)]
    for i, close in enumerate(local):
        seed_daily_bars(
            tmp_path,
            f"2026-09-{i + 1:02d}",
            [{"symbol": "AAPL", "close": close}],
        )
    client = MagicMock()
    client.get_candle_data.return_value = {
        "s": "ok",
        "c": [float(i) for i in range(10)],
    }

    closes = load_symbol_closes("AAPL", data_dir=tmp_path, client=client)
    assert closes == local


def test_load_symbol_closes_keeps_partial_provider_when_longer_than_local(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    seed_daily_bars(tmp_path, "2026-09-01", [{"symbol": "AAPL", "close": 1.0}])
    seed_daily_bars(tmp_path, "2026-09-02", [{"symbol": "AAPL", "close": 2.0}])
    client = MagicMock()
    client.get_candle_data.return_value = {
        "s": "ok",
        "c": [10.0, 11.0, 12.0, 13.0],
    }

    closes = load_symbol_closes("AAPL", data_dir=tmp_path, client=client)
    assert closes == [10.0, 11.0, 12.0, 13.0]


def test_closes_by_symbol_overlays_snapshot_and_skips_bad_latest():
    with patch(
        "src.alerts.price_history.load_symbol_closes",
        return_value=[100.0, 101.0],
    ) as loader:
        overlaid = closes_by_symbol(
            ["AAPL", "aapl"],
            [{"symbol": "AAPL", "close": 105.0}],
            prefer_provider=False,
        )
        ignored = closes_by_symbol(
            ["AAPL"],
            [{"symbol": "AAPL", "close": float("nan")}],
            prefer_provider=False,
        )

    assert overlaid == {"AAPL": [100.0, 105.0]}
    assert ignored == {"AAPL": [100.0, 101.0]}
    assert loader.call_count == 2
