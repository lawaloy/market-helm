"""Direct unit tests for alert rule predicates."""

import pytest

from src.alerts.alert_rules import (
    _compare,
    evaluate_price_threshold,
    evaluate_screening_match,
)


@pytest.mark.parametrize(
    ("operator", "value", "threshold", "expected"),
    [
        ("less_than", 9.0, 10.0, True),
        ("less_than", 10.0, 10.0, False),
        ("less_or_equal", 10.0, 10.0, True),
        ("less_or_equal", 10.1, 10.0, False),
        ("greater_than", 10.1, 10.0, True),
        ("greater_than", 10.0, 10.0, False),
        ("greater_or_equal", 10.0, 10.0, True),
        ("greater_or_equal", 9.9, 10.0, False),
        ("equal", 10.0, 10.0, True),
        ("equal", 10.01, 10.0, False),
    ],
)
def test_compare_operators(operator, value, threshold, expected):
    assert _compare(value, operator, threshold) is expected


def test_compare_rejects_unsupported_operator():
    with pytest.raises(ValueError, match="Unsupported operator"):
        _compare(1.0, "not_an_op", 1.0)


def test_price_threshold_defaults_to_less_than_and_zero():
    assert evaluate_price_threshold({}, {"close": -1.0}) is True
    assert evaluate_price_threshold({}, {"close": 0.0}) is False
    assert evaluate_price_threshold({}, {}) is False  # missing close -> 0


def test_price_threshold_boundary_and_operator():
    stock = {"close": "25.5"}
    assert evaluate_price_threshold(
        {"operator": "greater_or_equal", "value": "25.5"}, stock
    ) is True
    assert evaluate_price_threshold(
        {"operator": "greater_than", "value": 25.5}, stock
    ) is False


def test_screening_match_passes_with_no_filters():
    assert evaluate_screening_match({}, {"close": 10, "volume": 1}) is True
    assert evaluate_screening_match({"filters": {}}, {}) is True


def test_screening_match_volume_and_change_filters():
    stock = {"volume": 1_000_000, "change_percent": -2.5, "close": 50.0}
    assert evaluate_screening_match(
        {"filters": {"volume_threshold": 500_000, "min_daily_change_pct": 2.0}},
        stock,
    ) is True
    assert evaluate_screening_match(
        {"filters": {"volume_threshold": 2_000_000}}, stock
    ) is False
    assert evaluate_screening_match(
        {"filters": {"min_daily_change_pct": 3.0}}, stock
    ) is False


def test_screening_match_price_band_and_missing_fields():
    assert evaluate_screening_match(
        {"filters": {"price_min": 40, "price_max": 60}},
        {"close": 50},
    ) is True
    assert evaluate_screening_match(
        {"filters": {"price_min": 40}},
        {"close": 39.9},
    ) is False
    assert evaluate_screening_match(
        {"filters": {"price_max": 60}},
        {"close": 60.1},
    ) is False
    # Missing fields coerce to 0 and fail min filters
    assert evaluate_screening_match(
        {"filters": {"volume_threshold": 1, "price_min": 1}},
        {},
    ) is False
