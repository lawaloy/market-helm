"""get_indices_to_track must ignore non-list / dirty indices_to_track values."""

from unittest.mock import mock_open, patch

from src.core.config import _DEFAULT_INDICES, get_indices_to_track


@patch("pathlib.Path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"indices_to_track": "S&P 500"}',
)
def test_string_indices_to_track_falls_back_to_defaults(mock_file, mock_exists) -> None:
    """A bare string would otherwise iterate characters into the fetch loop."""
    assert get_indices_to_track() == _DEFAULT_INDICES


@patch("pathlib.Path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"indices_to_track": {"name": "S&P 500"}}',
)
def test_object_indices_to_track_falls_back(mock_file, mock_exists) -> None:
    assert get_indices_to_track() == _DEFAULT_INDICES


@patch("pathlib.Path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"indices_to_track": ["  S&P 500  ", "", null, 12, "NASDAQ-100"]}',
)
def test_mixed_list_keeps_only_non_empty_strings(mock_file, mock_exists) -> None:
    assert get_indices_to_track() == ["S&P 500", "NASDAQ-100"]


@patch("pathlib.Path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data='["S&P 500"]')
def test_root_non_object_falls_back(mock_file, mock_exists) -> None:
    assert get_indices_to_track() == _DEFAULT_INDICES
