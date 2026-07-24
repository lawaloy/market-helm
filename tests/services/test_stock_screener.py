"""Tests for stock screener scoring and qualification edges."""

from unittest.mock import MagicMock

from src.services.stock_screener import StockScreener


def _screener() -> StockScreener:
    return StockScreener(api_client=MagicMock())


def test_calculate_score_rewards_liquid_movers():
    screener = _screener()
    strong = screener.calculate_score(
        {
            "volume": 12_000_000,
            "change_percent": 8.0,
            "close": 100.0,
            "market_cap": 50_000_000_000,
        }
    )
    weak = screener.calculate_score(
        {
            "volume": 100,
            "change_percent": 0.1,
            "close": 1.0,
            "market_cap": 1,
        }
    )

    assert strong > 70
    assert weak < 5
    assert strong > weak


def test_score_helpers_cover_boundary_bands():
    screener = _screener()

    assert screener._score_volume(500_000) == 0.0
    assert screener._score_volume(1_000_000) == 50.0
    assert screener._score_volume(10_000_000) == 100.0

    assert screener._score_price_change(1.0) == 0.0
    assert screener._score_price_change(2.0) == 50.0
    assert screener._score_price_change(-12.0) == 100.0

    assert screener._score_price_range(50.0) == 100.0
    assert screener._score_price_range(5.0) == 25.0
    assert screener._score_price_range(2_000.0) == 0.0

    assert screener._score_market_cap(500_000_000) == 0.0
    assert screener._score_market_cap(1_000_000_000) == 50.0
    assert screener._score_market_cap(100_000_000_000) == 100.0


def test_screen_stock_returns_none_when_api_payload_missing():
    client = MagicMock()
    client.get_stock_data_for_screening.return_value = None
    screener = StockScreener(api_client=client)

    assert screener.screen_stock("AAPL") is None


def test_get_qualified_symbols_orders_by_score_and_respects_top_n(monkeypatch):
    screener = StockScreener(
        filters_config={
            **StockScreener(api_client=MagicMock()).filters,
            "top_n": 2,
        },
        api_client=MagicMock(),
    )

    payloads = {
        "LOW": {"symbol": "LOW", "volume": 2_000_000, "change_percent": 2.0, "close": 20.0, "market_cap": 2_000_000_000},
        "MID": {"symbol": "MID", "volume": 5_000_000, "change_percent": 4.0, "close": 40.0, "market_cap": 10_000_000_000},
        "HIGH": {"symbol": "HIGH", "volume": 20_000_000, "change_percent": 12.0, "close": 80.0, "market_cap": 200_000_000_000},
        "FAIL": None,
    }

    def fake_screen(symbol: str):
        data = payloads[symbol]
        if data is None:
            return None
        scored = dict(data)
        scored["screener_score"] = screener.calculate_score(scored)
        return scored

    monkeypatch.setattr(screener, "screen_stock", fake_screen)
    monkeypatch.setattr("src.services.stock_screener.time.sleep", lambda _seconds: None)

    assert screener.get_qualified_symbols(["LOW", "FAIL", "HIGH", "MID"]) == ["HIGH", "MID"]
