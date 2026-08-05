"""All-nonfinite projection aggregates must stay JSON-safe."""

import json
import math

from src.analysis.projector import StockProjector


def test_projection_summary_all_nan_averages_are_finite() -> None:
    """All-NaN confidence/expected_change must not poison summary JSON."""
    projector = StockProjector()
    projections = {
        "A": {
            "symbol": "A",
            "target_mid": 100.0,
            "confidence": float("nan"),
            "expected_change_percent": float("nan"),
            "recommendation": "HOLD",
            "trend": "sideways",
        },
        "B": {
            "symbol": "B",
            "target_mid": 90.0,
            "confidence": float("nan"),
            "expected_change_percent": float("inf"),
            "recommendation": "STRONG BUY",
            "trend": "up",
        },
    }
    summary = projector.generate_projection_summary(projections)

    assert summary["average_confidence"] == 0.0
    assert summary["average_expected_change"] == 0.0
    assert summary["top_opportunities"]["strong_buys"] == []
    assert math.isfinite(summary["average_confidence"])
    assert math.isfinite(summary["average_expected_change"])
    encoded = json.dumps(summary)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
