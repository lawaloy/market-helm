"""Tests for alert rule non-finite numeric guards."""

from src.alerts.alert_rules import evaluate_price_threshold, evaluate_screening_match


class TestEvaluatePriceThreshold:
    def test_finite_greater_than_matches(self):
        assert evaluate_price_threshold(
            {"operator": "greater_than", "value": 100},
            {"close": 150},
        )

    def test_inf_close_does_not_match_greater_than(self):
        """float('inf') > threshold is True in Python; must not fire alerts."""
        assert not evaluate_price_threshold(
            {"operator": "greater_than", "value": 100},
            {"close": float("inf")},
        )

    def test_nan_close_does_not_match(self):
        assert not evaluate_price_threshold(
            {"operator": "less_than", "value": 100},
            {"close": float("nan")},
        )

    def test_inf_threshold_does_not_match(self):
        assert not evaluate_price_threshold(
            {"operator": "less_than", "value": float("inf")},
            {"close": 50},
        )


class TestEvaluateScreeningMatch:
    def test_finite_filters_match(self):
        assert evaluate_screening_match(
            {
                "filters": {
                    "volume_threshold": 1_000_000,
                    "min_daily_change_pct": 1.0,
                    "price_min": 10,
                    "price_max": 200,
                }
            },
            {"volume": 2_000_000, "change_percent": 2.5, "close": 50},
        )

    def test_inf_volume_does_not_match(self):
        """Inf volume would pass a finite volume_threshold check without a guard."""
        assert not evaluate_screening_match(
            {"filters": {"volume_threshold": 1_000_000}},
            {"volume": float("inf"), "change_percent": 2.0, "close": 50},
        )

    def test_nan_close_fails_price_bounds(self):
        assert not evaluate_screening_match(
            {"filters": {"price_min": 10, "price_max": 200}},
            {"volume": 1_000_000, "change_percent": 1.0, "close": float("nan")},
        )
