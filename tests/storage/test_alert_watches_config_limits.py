"""Cap alerts-per-config so one tenant cannot unbounded-sync the watch index."""

import pytest

from src.storage.alert_watches import (
    MAX_ALERTS_PER_CONFIG,
    InvalidAlertWatchConfig,
    list_watches_for_symbol,
    sync_watches_from_config,
    validate_watches_config,
)
from src.storage.database import init_database
from src.storage.user_alerts import save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts-limit.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("alerts-limit@example.com", "password123")["id"]


def _price_alert(alert_id: str, *, value: float = 100.0) -> dict:
    return {
        "id": alert_id,
        "enabled": True,
        "cooldown_minutes": 15,
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": value,
        },
        "notifications": ["log"],
    }


def test_validate_rejects_more_than_max_alerts(db_user) -> None:
    alerts = [_price_alert(f"a{i}") for i in range(MAX_ALERTS_PER_CONFIG + 1)]
    with pytest.raises(InvalidAlertWatchConfig, match="maximum of"):
        validate_watches_config(db_user, {"defaults": {}, "alerts": alerts})


def test_validate_accepts_exactly_max_alerts(db_user) -> None:
    # Distinct symbols so polish/dedupe cannot shrink below the cap.
    alerts = [
        {
            **_price_alert(f"a{i}", value=100 + i),
            "condition": {
                "type": "price_threshold",
                "symbol": f"S{i:04d}",
                "operator": "less_than",
                "value": 100 + i,
            },
        }
        for i in range(MAX_ALERTS_PER_CONFIG)
    ]
    validate_watches_config(db_user, {"defaults": {}, "alerts": alerts})


def test_oversized_config_does_not_replace_existing_watches(db_user) -> None:
    save_user_alerts_config(
        db_user,
        {"defaults": {}, "alerts": [_price_alert("keep-me", value=150)]},
    )
    assert len(list_watches_for_symbol("AAPL")) == 1

    oversized = [_price_alert(f"a{i}") for i in range(MAX_ALERTS_PER_CONFIG + 1)]
    with pytest.raises(InvalidAlertWatchConfig, match="maximum of"):
        save_user_alerts_config(db_user, {"defaults": {}, "alerts": oversized})

    watches = list_watches_for_symbol("AAPL")
    assert len(watches) == 1
    assert watches[0]["alert_id"] == "keep-me"


def test_validate_rejects_non_list_alerts(db_user) -> None:
    with pytest.raises(InvalidAlertWatchConfig, match="alerts' array"):
        validate_watches_config(db_user, {"defaults": {}, "alerts": {"id": "x"}})


def test_sync_respects_max_alerts_cap(db_user) -> None:
    oversized = [_price_alert(f"a{i}") for i in range(MAX_ALERTS_PER_CONFIG + 5)]
    with pytest.raises(InvalidAlertWatchConfig, match="maximum of"):
        sync_watches_from_config(db_user, {"defaults": {}, "alerts": oversized})
