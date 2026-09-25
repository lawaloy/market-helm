"""Tests for RSI and compound alert rule evaluators."""

from src.alerts.alert_rules import (
    MAX_COMPOUND_LEAVES,
    collect_rsi_symbols,
    evaluate_compound,
    evaluate_rsi_threshold,
    primary_watch_symbol,
)
from src.alerts.indicators import compute_rsi


def _rising_closes(n: int = 20, start: float = 100.0) -> list[float]:
    return [start + i for i in range(n)]


def _falling_closes(n: int = 20, start: float = 100.0) -> list[float]:
    return [start - i for i in range(n)]


def test_compute_rsi_high_on_steady_rise():
    rsi = compute_rsi(_rising_closes(20), period=14)
    # No down-closes → avg_loss is 0 and Wilder RSI is defined as 100.
    assert rsi == 100.0


def test_compute_rsi_low_on_steady_fall():
    rsi = compute_rsi(_falling_closes(20), period=14)
    assert rsi is not None
    assert rsi < 30


def test_compute_rsi_requires_period_plus_one_bars():
    assert compute_rsi(_rising_closes(14), period=14) is None
    assert compute_rsi(_rising_closes(15), period=14) is not None


def test_compute_rsi_undefined_when_flat_or_inputs_invalid():
    """No movement, bad period, or a poison close must not invent an RSI."""
    assert compute_rsi([100.0] * 20, period=14) is None
    assert compute_rsi(_rising_closes(20), period=1) is None
    assert compute_rsi(_rising_closes(20), period="nope") is None
    poisoned = _rising_closes(20)
    poisoned[3] = float("nan")
    assert compute_rsi(poisoned, period=14) is None
    assert compute_rsi(_rising_closes(20)[:-1] + ["x"], period=14) is None


def test_rsi_threshold_oversold_match():
    closes = _falling_closes(20)
    assert (
        evaluate_rsi_threshold(
            {
                "type": "rsi_threshold",
                "symbol": "AAPL",
                "period": 14,
                "operator": "less_than",
                "value": 30,
            },
            closes,
        )
        is True
    )
    assert (
        evaluate_rsi_threshold(
            {
                "type": "rsi_threshold",
                "operator": "greater_than",
                "value": 70,
                "period": 14,
            },
            closes,
        )
        is False
    )


def test_rsi_threshold_soft_fails_on_bad_inputs():
    assert evaluate_rsi_threshold({"operator": "less_than", "value": 30}, []) is False
    assert (
        evaluate_rsi_threshold(
            {"operator": "nope", "value": 30, "period": 14},
            _falling_closes(20),
        )
        is False
    )
    assert (
        evaluate_rsi_threshold(
            {"operator": "less_than", "value": float("nan"), "period": 14},
            _falling_closes(20),
        )
        is False
    )
    # Period bounds live on the evaluator (indicator itself only rejects < 2).
    assert (
        evaluate_rsi_threshold(
            {"operator": "less_than", "value": 30, "period": 1},
            _falling_closes(20),
        )
        is False
    )
    assert (
        evaluate_rsi_threshold(
            {"operator": "greater_than", "value": 70, "period": 51},
            _rising_closes(60),
        )
        is False
    )


def test_compound_and_requires_both_leaves():
    stocks = [{"symbol": "AAPL", "close": 140.0}]
    closes = {"AAPL": _falling_closes(20)}
    condition = {
        "type": "compound",
        "op": "and",
        "conditions": [
            {
                "type": "price_threshold",
                "symbol": "AAPL",
                "operator": "less_than",
                "value": 150,
            },
            {
                "type": "rsi_threshold",
                "symbol": "AAPL",
                "period": 14,
                "operator": "less_than",
                "value": 30,
            },
        ],
    }
    assert evaluate_compound(condition, stocks, closes_by_symbol=closes) == ["AAPL"]

    high_price = [{"symbol": "AAPL", "close": 160.0}]
    assert evaluate_compound(condition, high_price, closes_by_symbol=closes) == []


def test_compound_or_matches_either_leaf():
    stocks = [{"symbol": "AAPL", "close": 160.0}]
    closes = {"AAPL": _falling_closes(20)}
    condition = {
        "type": "compound",
        "op": "or",
        "conditions": [
            {
                "type": "price_threshold",
                "symbol": "AAPL",
                "operator": "less_than",
                "value": 150,
            },
            {
                "type": "rsi_threshold",
                "symbol": "AAPL",
                "period": 14,
                "operator": "less_than",
                "value": 30,
            },
        ],
    }
    assert evaluate_compound(condition, stocks, closes_by_symbol=closes) == ["AAPL"]


def test_compound_rejects_nested_and_unknown_ops():
    nested = {
        "type": "compound",
        "op": "and",
        "conditions": [
            {
                "type": "compound",
                "op": "or",
                "conditions": [
                    {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 150,
                    }
                ],
            }
        ],
    }
    assert evaluate_compound(nested, [{"symbol": "AAPL", "close": 1}], {}) == []
    assert (
        evaluate_compound(
            {"type": "compound", "op": "xor", "conditions": []},
            [],
            {},
        )
        == []
    )


def test_primary_watch_symbol_for_single_symbol_compound():
    condition = {
        "type": "compound",
        "op": "and",
        "conditions": [
            {
                "type": "price_threshold",
                "symbol": "AAPL",
                "operator": "less_than",
                "value": 150,
            },
            {
                "type": "rsi_threshold",
                "symbol": "AAPL",
                "period": 14,
                "operator": "less_than",
                "value": 30,
            },
        ],
    }
    assert primary_watch_symbol(condition) == "AAPL"
    mixed = {
        "type": "compound",
        "op": "and",
        "conditions": [
            {
                "type": "price_threshold",
                "symbol": "AAPL",
                "operator": "less_than",
                "value": 150,
            },
            {
                "type": "rsi_threshold",
                "symbol": "MSFT",
                "period": 14,
                "operator": "less_than",
                "value": 30,
            },
        ],
    }
    assert primary_watch_symbol(mixed) is None


def test_compound_rejects_more_than_max_leaves_even_when_all_match():
    stocks = [{"symbol": "AAPL", "close": 1.0}]
    leaves = [
        {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 10,
        }
        for _ in range(MAX_COMPOUND_LEAVES + 1)
    ]
    assert (
        evaluate_compound(
            {"type": "compound", "op": "and", "conditions": leaves},
            stocks,
            {},
        )
        == []
    )


def test_collect_rsi_symbols_walks_leaves_and_skips_junk():
    alerts = [
        None,
        "not-an-alert",
        {
            "id": "plain",
            "condition": {
                "type": "rsi_threshold",
                "symbol": " aapl ",
                "operator": "less_than",
                "value": 30,
            },
        },
        {
            "id": "combo",
            "condition": {
                "type": "compound",
                "op": "and",
                "conditions": [
                    {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 150,
                    },
                    {
                        "type": "rsi_threshold",
                        "symbol": "MSFT",
                        "operator": "greater_than",
                        "value": 70,
                    },
                    {
                        "type": "rsi_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 30,
                    },
                    "skip-me",
                ],
            },
        },
        {"id": "price-only", "condition": {"type": "price_threshold", "symbol": "NVDA"}},
    ]
    assert collect_rsi_symbols(alerts) == ["AAPL", "MSFT"]
