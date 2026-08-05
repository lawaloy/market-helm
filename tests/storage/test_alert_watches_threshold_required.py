"""price_threshold watches must include a finite numeric value at save/sync."""

import pytest

from src.storage.alert_watches import (
    InvalidAlertWatchConfig,
    list_watches_for_symbol,
    validate_watches_config,
)
from src.storage.database import init_database
from src.storage.user_alerts import save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "threshold-required.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("threshold-required@example.com", "password123")["id"]


def _alert(*, value=150, include_value: bool = True) -> dict:
    condition = {
        "type": "price_threshold",
        "symbol": "AAPL",
        "operator": "less_than",
    }
    if include_value:
        condition["value"] = value
    return {
        "id": "aapl-low",
        "enabled": True,
        "cooldown_minutes": 15,
        "condition": condition,
        "notifications": ["log"],
    }


@pytest.mark.parametrize(
    "bad_value",
    [None, "", "   ", "not-a-number"],
)
def test_validate_rejects_missing_or_invalid_threshold(db_user, bad_value) -> None:
    with pytest.raises(InvalidAlertWatchConfig, match="price threshold"):
        validate_watches_config(
            db_user,
            {"defaults": {}, "alerts": [_alert(value=bad_value)]},
        )


def test_validate_rejects_omitted_threshold_value(db_user) -> None:
    with pytest.raises(InvalidAlertWatchConfig, match="price threshold"):
        validate_watches_config(
            db_user,
            {"defaults": {}, "alerts": [_alert(include_value=False)]},
        )


def test_null_threshold_preserves_existing_watches(db_user) -> None:
    save_user_alerts_config(
        db_user,
        {"defaults": {}, "alerts": [_alert(value=150)]},
    )
    assert len(list_watches_for_symbol("AAPL")) == 1

    with pytest.raises(InvalidAlertWatchConfig, match="price threshold"):
        save_user_alerts_config(
            db_user,
            {"defaults": {}, "alerts": [_alert(value=None)]},
        )

    watches = list_watches_for_symbol("AAPL")
    assert len(watches) == 1
    assert watches[0]["alert_id"] == "aapl-low"


def test_validate_accepts_finite_numeric_string(db_user) -> None:
    validate_watches_config(
        db_user,
        {"defaults": {}, "alerts": [_alert(value="175.5")]},
    )
