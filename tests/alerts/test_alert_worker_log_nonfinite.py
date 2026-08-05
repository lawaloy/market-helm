"""log_check_result must not crash the worker loop on Inf/NaN triggered counts."""

import logging

import pytest

from src.alerts import alert_worker
from src.alerts.alert_worker import _coerce_triggered_count, log_check_result


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0, 0),
        (3, 3),
        ("2", 2),
        (None, 0),
        (float("nan"), 0),
        (float("inf"), 0),
        (float("-inf"), 0),
        ("nan", 0),
        (True, 1),
        ([], 0),
    ],
)
def test_coerce_triggered_count(raw, expected) -> None:
    assert _coerce_triggered_count(raw) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_log_check_result_tolerates_nonfinite_triggered(bad, caplog) -> None:
    # Previously: int(Inf) → OverflowError; int(NaN) → ValueError — aborted the loop.
    with caplog.at_level(logging.INFO, logger=alert_worker.logger.name):
        log_check_result(
            {
                "triggered": bad,
                "events": [{"alert_name": "x", "symbols": ["AAPL"]}],
                "last_data_date": "2026-06-09",
            }
        )
    assert "no triggers" in caplog.text.lower()
