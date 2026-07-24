"""Screening filter / condition shapes must soft-fail, not AttributeError."""

import pytest

from src.alerts.alert_rules import evaluate_price_threshold, evaluate_screening_match


class TestEvaluatePriceThresholdShapes:
    @pytest.mark.parametrize("bad_condition", [["x"], "nope", 12, None, True])
    def test_non_dict_condition_returns_false(self, bad_condition):
        assert not evaluate_price_threshold(bad_condition, {"close": 150})

    @pytest.mark.parametrize("bad_stock", [["x"], "AAPL", 12, None])
    def test_non_dict_stock_returns_false(self, bad_stock):
        assert not evaluate_price_threshold(
            {"operator": "greater_than", "value": 100},
            bad_stock,
        )


class TestEvaluateScreeningMatchFiltersShape:
    def test_missing_filters_defaults_to_match(self):
        assert evaluate_screening_match({}, {"volume": 1, "close": 50})

    @pytest.mark.parametrize("bad_filters", [None, ["x"], "volume_threshold", 3, True])
    def test_non_dict_filters_treated_as_empty(self, bad_filters):
        """filters: null/list previously AttributeError'd the whole evaluate pass."""
        assert evaluate_screening_match(
            {"filters": bad_filters},
            {"volume": 1, "change_percent": 1.0, "close": 50},
        )

    def test_valid_filters_still_enforce_bounds(self):
        assert not evaluate_screening_match(
            {"filters": {"price_min": 100}},
            {"volume": 1, "change_percent": 1.0, "close": 50},
        )

    @pytest.mark.parametrize("bad_condition", [["x"], None, "filters"])
    def test_non_dict_condition_returns_false(self, bad_condition):
        assert not evaluate_screening_match(bad_condition, {"close": 50})
