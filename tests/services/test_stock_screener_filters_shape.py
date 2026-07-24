"""StockScreener must soft-fail truthy non-dict filters and bad top_n."""

from unittest.mock import MagicMock

from src.services.stock_screener import StockScreener


def _defaults() -> dict:
    return StockScreener(api_client=MagicMock())._get_default_filters()


def test_truthy_non_dict_filters_fall_back_to_defaults():
    for bad in (["volume_threshold"], "not-a-dict", 42, True):
        screener = StockScreener(filters_config=bad, api_client=MagicMock())
        assert isinstance(screener.filters, dict)
        assert screener.filters["volume_threshold"] == _defaults()["volume_threshold"]
        assert screener._score_volume(1_000_000) == 50.0


def test_non_dict_weights_fall_back_to_defaults():
    screener = StockScreener(
        filters_config={**_defaults(), "weights": ["volume"]},
        api_client=MagicMock(),
    )
    assert isinstance(screener.filters["weights"], dict)
    score = screener.calculate_score(
        {
            "volume": 12_000_000,
            "change_percent": 8.0,
            "close": 100.0,
            "market_cap": 50_000_000_000,
        }
    )
    assert score > 70


def test_bad_top_n_falls_back_instead_of_slicing_error(monkeypatch):
    for bad_top_n in ("abc", float("nan"), float("inf"), None, object()):
        screener = StockScreener(
            filters_config={**_defaults(), "top_n": bad_top_n},
            api_client=MagicMock(),
        )
        assert screener._safe_top_n() == 100

        payloads = {
            "A": {
                "symbol": "A",
                "volume": 20_000_000,
                "change_percent": 12.0,
                "close": 80.0,
                "market_cap": 200_000_000_000,
            },
            "B": {
                "symbol": "B",
                "volume": 5_000_000,
                "change_percent": 4.0,
                "close": 40.0,
                "market_cap": 10_000_000_000,
            },
        }

        def fake_screen(symbol: str):
            scored = dict(payloads[symbol])
            scored["screener_score"] = screener.calculate_score(scored)
            return scored

        monkeypatch.setattr(screener, "screen_stock", fake_screen)
        monkeypatch.setattr("src.services.stock_screener.time.sleep", lambda _seconds: None)
        assert screener.get_qualified_symbols(["A", "B"]) == ["A", "B"]


def test_float_top_n_truncates_to_int(monkeypatch):
    screener = StockScreener(
        filters_config={**_defaults(), "top_n": 1.9},
        api_client=MagicMock(),
    )
    assert screener._safe_top_n() == 1

    payloads = {
        "HIGH": {
            "symbol": "HIGH",
            "volume": 20_000_000,
            "change_percent": 12.0,
            "close": 80.0,
            "market_cap": 200_000_000_000,
        },
        "LOW": {
            "symbol": "LOW",
            "volume": 2_000_000,
            "change_percent": 2.0,
            "close": 20.0,
            "market_cap": 2_000_000_000,
        },
    }

    def fake_screen(symbol: str):
        scored = dict(payloads[symbol])
        scored["screener_score"] = screener.calculate_score(scored)
        return scored

    monkeypatch.setattr(screener, "screen_stock", fake_screen)
    monkeypatch.setattr("src.services.stock_screener.time.sleep", lambda _seconds: None)
    assert screener.get_qualified_symbols(["LOW", "HIGH"]) == ["HIGH"]


def test_negative_top_n_clamps_to_empty_selection(monkeypatch):
    screener = StockScreener(
        filters_config={**_defaults(), "top_n": -3},
        api_client=MagicMock(),
    )
    assert screener._safe_top_n() == 0

    def fake_screen(symbol: str):
        return {
            "symbol": symbol,
            "volume": 20_000_000,
            "change_percent": 12.0,
            "close": 80.0,
            "market_cap": 200_000_000_000,
            "screener_score": 99.0,
        }

    monkeypatch.setattr(screener, "screen_stock", fake_screen)
    monkeypatch.setattr("src.services.stock_screener.time.sleep", lambda _seconds: None)
    assert screener.get_qualified_symbols(["AAPL"]) == []
