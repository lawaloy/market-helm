"""Finnhub quote NaN/Inf must not poison CSV / dashboard consumers."""

from unittest.mock import Mock, patch

from src.services.api_client import FinnhubClient


def _client_with_quote(quote: dict) -> FinnhubClient:
    client = FinnhubClient(api_key="test_api_key_12345")
    client.get_quote = Mock(return_value=quote)
    client.get_company_profile = Mock(return_value={"name": "Test Co", "exchange": "US"})
    return client


def test_screening_skips_nan_close() -> None:
    client = _client_with_quote({"c": float("nan"), "pc": 100.0, "v": 1_000_000})
    assert client.get_stock_data_for_screening("BAD") is None


def test_screening_skips_inf_close() -> None:
    client = _client_with_quote({"c": float("inf"), "pc": 100.0, "v": 1_000_000})
    assert client.get_stock_data_for_screening("BAD") is None


def test_screening_coerces_inf_volume_to_zero() -> None:
    client = _client_with_quote({"c": 150.0, "pc": 148.0, "v": float("inf")})
    data = client.get_stock_data_for_screening("AAPL")
    assert data is not None
    assert data["close"] == 150.0
    assert data["volume"] == 0.0
    assert data["change_percent"] == (150.0 - 148.0) / 148.0 * 100


def test_screening_falls_back_when_previous_close_nonfinite() -> None:
    client = _client_with_quote({"c": 150.0, "pc": float("nan"), "v": 10})
    data = client.get_stock_data_for_screening("AAPL")
    assert data is not None
    assert data["change_percent"] == 0.0


def test_stock_data_skips_nan_close() -> None:
    client = _client_with_quote(
        {"c": float("nan"), "pc": 100.0, "v": 1, "o": 1, "h": 1, "l": 1}
    )
    assert client.get_stock_data("BAD", include_profile=False) is None


def test_stock_data_coerces_nonfinite_ohlc_and_volume() -> None:
    client = _client_with_quote(
        {
            "c": 150.0,
            "pc": 148.0,
            "v": float("-inf"),
            "o": float("nan"),
            "h": float("inf"),
            "l": None,
        }
    )
    data = client.get_stock_data("AAPL", include_profile=True)
    assert data is not None
    assert data["close"] == 150.0
    assert data["open"] == 150.0
    assert data["high"] == 150.0
    assert data["low"] == 150.0
    assert data["volume"] == 0.0
    assert data["name"] == "Test Co"


@patch("requests.Session")
def test_stock_data_still_returns_finite_quote(mock_session) -> None:
    """Sanity: normal quotes still flow through after finite guards."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "c": 150.0,
        "pc": 148.0,
        "v": 5_000_000,
        "o": 149.0,
        "h": 151.0,
        "l": 147.0,
    }
    response.raise_for_status = Mock()
    session = Mock()
    session.get.return_value = response
    mock_session.return_value = session

    client = FinnhubClient(api_key="test_api_key_12345")
    client.session = session
    client.rate_limiter.wait_if_needed = Mock()
    client.get_company_profile = Mock(return_value={})

    data = client.get_stock_data("AAPL", include_profile=False)
    assert data["close"] == 150.0
    assert data["volume"] == 5_000_000
