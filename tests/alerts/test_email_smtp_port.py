"""SMTP port parsing must reject Inf / out-of-range values without raising."""

import math

from src.alerts.notifiers.email_delivery import build_smtp_backend


def _smtp_alert(**overrides):
    base = {
        "smtp_host": "smtp.example.com",
        "smtp_user": "user@example.com",
        "smtp_password": "secret",
        "smtp_port": 587,
    }
    base.update(overrides)
    return base


def test_build_smtp_backend_accepts_valid_port() -> None:
    backend = build_smtp_backend(_smtp_alert(smtp_port=587))
    assert backend is not None
    assert backend._port == 587


def test_build_smtp_backend_rejects_inf_port() -> None:
    assert build_smtp_backend(_smtp_alert(smtp_port=math.inf)) is None
    assert build_smtp_backend(_smtp_alert(smtp_port=float("inf"))) is None


def test_build_smtp_backend_rejects_nan_port() -> None:
    assert build_smtp_backend(_smtp_alert(smtp_port=math.nan)) is None


def test_build_smtp_backend_rejects_out_of_range_port() -> None:
    assert build_smtp_backend(_smtp_alert(smtp_port=0)) is None
    assert build_smtp_backend(_smtp_alert(smtp_port=70000)) is None


def test_build_smtp_backend_rejects_non_numeric_port() -> None:
    assert build_smtp_backend(_smtp_alert(smtp_port="not-a-port")) is None
