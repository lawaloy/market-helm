"""Close-history loader for RSI alert evaluation."""

from unittest.mock import MagicMock

from src.alerts.price_history import (
    closes_from_candle_payload,
    load_symbol_closes,
    load_symbol_closes_from_csv,
    merge_latest_close,
)


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
