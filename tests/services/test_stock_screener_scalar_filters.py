"""Dirty filters.json scalars must soft-coerce instead of emptying the screen."""

from unittest.mock import MagicMock

import pytest

from src.services.stock_screener import StockScreener


def _defaults() -> dict:
    return StockScreener(api_client=MagicMock())._get_default_filters()


def _liquid_mover() -> dict:
    return {
        "volume": 12_000_000,
        "change_percent": 8.0,
        "close": 100.0,
        "market_cap": 50_000_000_000,
    }


@pytest.mark.parametrize(
    "key,bad",
    [
        ("volume_threshold", "lots"),
        ("volume_threshold", None),
        ("volume_threshold", float("nan")),
        ("min_daily_change_pct", "x"),
        ("price_min", "cheap"),
        ("price_max", []),
        ("market_cap_min", {"a": 1}),
        ("market_cap_min", float("-inf")),
        ("price_min", float("inf")),
    ],
)
def test_dirty_scalar_filters_fall_back_to_defaults(key, bad):
    """Hand-edited non-numeric / non-finite thresholds previously TypeError'd scoring."""
    baseline = StockScreener(api_client=MagicMock()).calculate_score(_liquid_mover())
    screener = StockScreener(
        filters_config={**_defaults(), key: bad},
        api_client=MagicMock(),
    )
    assert screener.filters[key] == _defaults()[key]
    score = screener.calculate_score(_liquid_mover())
    assert score == pytest.approx(baseline)


def test_partial_weights_merge_missing_keys():
    screener = StockScreener(
        filters_config={**_defaults(), "weights": {"volume": 0.5}},
        api_client=MagicMock(),
    )
    weights = screener.filters["weights"]
    assert weights["volume"] == pytest.approx(0.5)
    assert weights["price_change"] == pytest.approx(_defaults()["weights"]["price_change"])
    assert screener.calculate_score(_liquid_mover()) > 0


def test_non_numeric_weight_falls_back_to_default():
    defaults = _defaults()
    screener = StockScreener(
        filters_config={
            **defaults,
            "weights": {
                **defaults["weights"],
                "volume": "heavy",
            },
        },
        api_client=MagicMock(),
    )
    assert screener.filters["weights"]["volume"] == pytest.approx(
        defaults["weights"]["volume"]
    )
    assert screener.calculate_score(_liquid_mover()) > 70


def test_caller_filters_dict_is_not_mutated():
    """Coercion must copy config so shared filters.json loads stay pristine."""
    cfg = {**_defaults(), "volume_threshold": "nope"}
    StockScreener(filters_config=cfg, api_client=MagicMock())
    assert cfg["volume_threshold"] == "nope"
