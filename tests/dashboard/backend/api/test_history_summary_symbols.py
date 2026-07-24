"""History summary/symbols must not leak None/NaN as NONE/NAN tickers."""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd

from dashboard.backend.api.history import get_historical_summary, get_tracked_symbols


def _proj_frame(symbols, names=None):
    n = len(symbols)
    return pd.DataFrame(
        {
            "symbol": symbols,
            "name": names or ["Name"] * n,
            "confidence": [70.0] * n,
            "expected_change_percent": [1.0] * n,
            "recommendation": ["HOLD"] * n,
        }
    )


def test_historical_summary_skips_sentinel_and_padded_symbols():
    """Corrupt projection symbols must not appear as NONE/NAN/blank in the API."""
    loader = MagicMock()
    loader.get_available_dates.return_value = ["2026-07-24"]
    loader.load_projections.return_value = _proj_frame(
        [" aapl ", None, float("nan"), "", "  ", "msft", "NONE"],
        ["Apple", "Nope", "Nope", "Nope", "Nope", "Microsoft", "Nope"],
    )

    with patch("dashboard.backend.api.history.get_data_loader", return_value=loader):
        with patch(
            "dashboard.backend.api.history._resolve_company_names",
            side_effect=lambda symbols: {s: s for s in symbols},
        ):
            payload = asyncio.run(get_historical_summary(days=7))

    assert payload["symbols"] == ["AAPL", "MSFT"]
    assert "NONE" not in payload["symbols"]
    assert "NAN" not in payload["symbols"]
    assert "" not in payload["symbols"]
    assert payload["names"]["AAPL"] == "Apple"
    assert payload["names"]["MSFT"] == "Microsoft"


def test_tracked_symbols_fallback_normalizes_dirty_projection_symbols():
    """When the index catalog is empty, fallback must still drop sentinels."""
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-07-24"
    loader.load_projections.return_value = _proj_frame(
        [None, float("nan"), " goog ", "", "NONE"],
        ["Nope", "Nope", "Alphabet", "Nope", "Nope"],
    )

    with patch("dashboard.backend.api.history.get_data_loader", return_value=loader):
        with patch(
            "dashboard.backend.api.history.build_symbol_catalog",
            return_value=([], {}),
        ):
            with patch(
                "dashboard.backend.api.history.load_index_symbol_names",
                return_value={},
            ):
                payload = asyncio.run(get_tracked_symbols())

    assert payload["symbols"] == ["GOOG"]
    assert payload["names"] == {"GOOG": "GOOG"}
    assert "NONE" not in payload["symbols"]
    assert "NAN" not in payload["symbols"]
    assert payload["date"] == "2026-07-24"
