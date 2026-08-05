"""GET /api/data-info must soft-fail unreadable data dirs as 404, not 500."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_data_info_404_when_available_dates_raises_oserror():
    """Loader method OSError after construction must map to 404 for autofetch."""
    loader = MagicMock()
    loader.data_dir = "/data"
    loader.get_latest_date.return_value = "2026-01-15"
    loader.needs_fetch_for_latest_trading_day.return_value = False
    loader.get_available_dates.side_effect = OSError("permission denied")

    with patch(
        "dashboard.backend.services.data_loader.get_data_loader",
        return_value=loader,
    ), patch(
        "dashboard.backend.services.data_loader.get_most_recent_trading_day",
        return_value="2026-01-16",
    ):
        client = TestClient(app)
        r = client.get("/api/data-info")

    assert r.status_code == 404
    assert r.json()["detail"] == "No data available."


def test_data_info_404_when_get_latest_date_raises_value_error():
    """ValueError from loader status methods must stay a 404, not a 500."""
    loader = MagicMock()
    loader.data_dir = "/data"
    loader.get_latest_date.side_effect = ValueError("Data directory unreadable")

    with patch(
        "dashboard.backend.services.data_loader.get_data_loader",
        return_value=loader,
    ):
        client = TestClient(app)
        r = client.get("/api/data-info")

    assert r.status_code == 404
    assert r.json()["detail"] == "No data available."
