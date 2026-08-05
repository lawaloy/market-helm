"""Demo AI summary must soft-fail dirty top-mover shapes."""

from src.analysis.ai_summarizer import AISummarizer


def test_demo_summary_skips_non_dict_and_blank_symbol_movers() -> None:
    summarizer = AISummarizer()
    analysis = {
        "summary": {
            "gainers": 3,
            "losers": 2,
            "average_change_percent": 1.25,
        },
        "top_gainers": [None, "AAPL", {"symbol": "  ", "change_percent": 9.0}, {"symbol": "GOOD", "change_percent": 4.5}],
        "top_losers": [{"change_percent": -3.0}, {"symbol": "DROP", "change_percent": -2.25}],
    }

    text = summarizer.generate_demo_summary(analysis, {})

    assert "averaging 1.25% change overall" in text
    assert "GOOD led gains with a 4.50% increase" in text
    assert "DROP declined 2.25%" in text
    assert "None" not in text
    assert "  led gains" not in text
