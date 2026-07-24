"""Demo AI summary must tolerate null / NaN / Inf rollup floats."""

import math

from src.analysis.ai_summarizer import AISummarizer


def test_demo_summary_coerces_null_average_change() -> None:
    summarizer = AISummarizer()
    analysis = {
        "summary": {
            "gainers": 4,
            "losers": 1,
            "average_change_percent": None,
        },
        "top_gainers": [],
        "top_losers": [],
    }
    text = summarizer.generate_demo_summary(analysis, {})
    assert "averaging 0.00% change overall" in text
    assert "positive" in text


def test_demo_summary_coerces_nan_mover_and_exchange_percents() -> None:
    summarizer = AISummarizer()
    analysis = {
        "summary": {
            "gainers": 2,
            "losers": 5,
            "average_change_percent": float("nan"),
        },
        "top_gainers": [{"symbol": "AAA", "change_percent": math.nan}],
        "top_losers": [{"symbol": "BBB", "change_percent": None}],
    }
    exchange = {
        "S&P 500": {"average_change_percent": float("inf")},
        "NASDAQ-100": {"average_change_percent": 0.4},
    }
    text = summarizer.generate_demo_summary(analysis, exchange)
    assert "averaging 0.00% change overall" in text
    assert "AAA led gains with a 0.00% increase" in text
    assert "BBB declined 0.00%" in text
    # Inf exchange avg ranks highest numerically once coerced? Inf → 0.0,
    # so NASDAQ-100 (0.4) should win.
    assert "NASDAQ-100" in text
    assert "0.40% gain" in text
