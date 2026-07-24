"""Truthy non-dict alerts.json defaults must soft-fail to {}, not crash polish."""

import pytest

from src.alerts.alert_paths import (
    polish_alerts_config,
    strip_webhook_secrets_from_config,
)


@pytest.mark.parametrize("bad_defaults", [["x"], "ab", 123, True, 3.14])
def test_polish_tolerates_truthy_non_dict_defaults(bad_defaults) -> None:
    polished = polish_alerts_config(
        {
            "defaults": bad_defaults,
            "alerts": [
                {
                    "id": "keep",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": ">",
                        "value": 100,
                    },
                    "notifications": ["log"],
                }
            ],
        },
        seed_env_email=False,
    )
    assert polished["defaults"] == {}
    assert len(polished["alerts"]) == 1
    assert polished["alerts"][0]["id"] == "keep"


@pytest.mark.parametrize("bad_defaults", [["x"], "ab", 123, True])
def test_strip_webhook_tolerates_truthy_non_dict_defaults(bad_defaults) -> None:
    cleaned = strip_webhook_secrets_from_config(
        {
            "defaults": bad_defaults,
            "alerts": [
                {
                    "id": "w1",
                    "webhook_url": "https://hooks.example/secret",
                    "notifications": ["webhook"],
                }
            ],
        }
    )
    assert cleaned["defaults"] == {}
    assert "webhook_url" not in cleaned["alerts"][0]


def test_polish_preserves_valid_defaults_dict(monkeypatch) -> None:
    monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
    polished = polish_alerts_config(
        {"defaults": {"email_to": "ops@example.com"}, "alerts": []},
        seed_env_email=False,
    )
    assert polished["defaults"]["email_to"] == "ops@example.com"
