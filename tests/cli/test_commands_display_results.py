"""CLI display_results must tolerate None/NaN/Inf numeric cells."""

from src.cli.commands import (
    _fmt_money,
    _fmt_number,
    _fmt_pct,
    display_results,
)


def test_fmt_helpers_reject_none_and_nonfinite() -> None:
    assert _fmt_number(1.234) == "1.23"
    assert _fmt_number(None) == "—"
    assert _fmt_number(float("nan")) == "—"
    assert _fmt_number(float("inf")) == "—"
    assert _fmt_number(-2.5, signed=True) == "-2.50"
    assert _fmt_pct(1.5) == "1.50%"
    assert _fmt_pct(None) == "—"
    assert _fmt_pct(2.5, signed=True) == "+2.50%"
    assert _fmt_money(12.5) == "$12.50"
    assert _fmt_money(None) == "—"
    assert _fmt_money(float("nan")) == "—"


def test_display_results_survives_none_summary_and_gainer_cells(caplog) -> None:
    """None in :.2f previously TypeError'd and made main() exit(1) after save."""
    with caplog.at_level("INFO"):
        display_results(
            {
                "success": True,
                "analysis": {
                    "summary": {
                        "total_stocks": 1,
                        "gainers": 1,
                        "losers": 0,
                        "unchanged": 0,
                        "average_change_percent": None,
                    },
                    "top_gainers": [
                        {
                            "symbol": "AAPL",
                            "name": "Apple",
                            "change_percent": None,
                            "close": None,
                        }
                    ],
                    "top_losers": [
                        {
                            "symbol": "MSFT",
                            "name": "Microsoft",
                            "change_percent": float("nan"),
                            "close": float("inf"),
                        }
                    ],
                },
                "index_comparison": {
                    "S&P 500": {
                        "stock_count": 1,
                        "average_change_percent": float("nan"),
                        "gainers": 0,
                        "losers": 0,
                    }
                },
                "metadata": {"date": "2026-07-24"},
                "file_paths": {
                    "data": "/tmp/daily.csv",
                    "summary": "/tmp/summary.json",
                },
            }
        )

    text = caplog.text
    assert "Average Change: —" in text
    assert "AAPL" in text
    assert "MSFT" in text
    assert "—" in text
    assert "Daily tracking complete!" in text
    assert "Data saved to: /tmp/daily.csv" in text


def test_display_results_survives_null_projection_targets(caplog) -> None:
    with caplog.at_level("INFO"):
        display_results(
            {
                "success": True,
                "analysis": {},
                "projection_summary": {
                    "total_projections": 1,
                    "average_confidence": None,
                    "average_expected_change": float("inf"),
                    "top_opportunities": {
                        "strong_buys": [{"symbol": "AAPL"}],
                        "strong_sells": [{"symbol": "MSFT"}],
                    },
                },
                "projections": {
                    "AAPL": {
                        "symbol": "AAPL",
                        "target_mid": None,
                        "expected_change_percent": float("nan"),
                        "confidence": 80,
                        "reason": "momentum",
                    },
                    "MSFT": {
                        "symbol": "MSFT",
                        "target_mid": float("inf"),
                        "expected_change_percent": None,
                        "confidence": 40,
                        "reason": "weak",
                    },
                },
                "metadata": {},
            }
        )

    text = caplog.text
    assert "Average Confidence: —" in text
    assert "Expected Market Move: —" in text
    assert "AAPL" in text
    assert "MSFT" in text
    assert "Daily tracking complete!" in text


def test_display_results_logs_failure_without_raising(caplog) -> None:
    with caplog.at_level("ERROR"):
        display_results({"success": False, "error": "boom"})
    assert "Workflow failed: boom" in caplog.text


def test_display_results_survives_nested_non_dict_shapes(caplog) -> None:
    """Corrupt summary JSON nests must not exit(1) after a successful save."""
    with caplog.at_level("INFO"):
        display_results(
            {
                "success": True,
                "analysis": {
                    "summary": "not-a-dict",
                    "top_gainers": [
                        "AAPL",
                        {
                            "symbol": "MSFT",
                            "name": "Microsoft",
                            "change_percent": 1.5,
                            "close": 400.0,
                        },
                    ],
                    "top_losers": [None, 42],
                },
                "index_comparison": {
                    "S&P 500": "bad",
                    "NASDAQ": {
                        "stock_count": 2,
                        "average_change_percent": 0.5,
                        "gainers": 1,
                        "losers": 1,
                    },
                },
                "projection_summary": {
                    "total_projections": 1,
                    "average_confidence": 70,
                    "average_expected_change": 1.0,
                    "recommendations": ["buy"],
                    "top_opportunities": {
                        "strong_buys": [
                            "junk",
                            {"symbol": "AAPL"},
                        ],
                        "strong_sells": "not-a-list",
                    },
                },
                "projections": {
                    "AAPL": {
                        "symbol": "AAPL",
                        "target_mid": 200.0,
                        "expected_change_percent": 2.0,
                        "confidence": 80,
                        "reason": "ok",
                    },
                    "MSFT": "not-a-projection",
                },
                "metadata": ["not", "a", "dict"],
                "file_paths": "not-a-dict",
            }
        )

    text = caplog.text
    assert "MSFT" in text
    assert "NASDAQ" in text
    assert "AAPL" in text
    assert "Daily tracking complete!" in text
    # Non-dict summary/recommendations/file_paths must be skipped, not crash
    assert "Total Stocks Tracked" not in text
    assert "Recommendation Breakdown" not in text
    assert "Data saved to:" not in text


def test_display_results_coerces_top_level_non_dict_sections(caplog) -> None:
    with caplog.at_level("INFO"):
        display_results(
            {
                "success": True,
                "analysis": "corrupt",
                "index_comparison": ["x"],
                "projections": ["x"],
                "projection_summary": "corrupt",
                "metadata": None,
                "file_paths": None,
            }
        )
    assert "Daily tracking complete!" in caplog.text
