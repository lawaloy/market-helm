"""Tests for ticker normalization helpers."""

import math

import pytest

from src.utils.tickers import normalize_ticker


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("aapl", "AAPL"),
        (" AAPL ", "AAPL"),
        ("msft", "MSFT"),
        ("", None),
        ("   ", None),
        (None, None),
        (float("nan"), None),
        ("nan", None),
        ("NaN", None),
        ("none", None),
        ("NULL", None),
        ("<NA>", None),
        ("BRK.B", "BRK.B"),
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


def test_normalize_ticker_rejects_nan_float_via_math():
    assert math.isnan(float("nan"))
    assert normalize_ticker(float("nan")) is None
