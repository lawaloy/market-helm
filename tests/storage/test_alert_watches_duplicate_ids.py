"""Duplicate alert ids must raise InvalidAlertWatchConfig before PK IntegrityError."""

import pytest

from src.storage.alert_watches import (
    InvalidAlertWatchConfig,
    list_watches_for_symbol,
    sync_watches_from_config,
    validate_watches_config,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "dup-watches.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("dup-watches@example.com", "password123")["id"]


def _price_alert(alert_id: str, symbol: str = "AAPL"):
    return {
        "id": alert_id,
        "enabled": True,
        "condition": {
            "type": "price_threshold",
            "symbol": symbol,
            "operator": "less_than",
            "value": 200,
        },
    }


def test_validate_rejects_duplicate_alert_ids(db_user) -> None:
    with pytest.raises(InvalidAlertWatchConfig, match="Duplicate alert id"):
        validate_watches_config(
            db_user,
            {
                "defaults": {},
                "alerts": [
                    _price_alert("same"),
                    _price_alert(" same ", symbol="MSFT"),
                ],
            },
        )


def test_sync_rejects_duplicates_without_mutating_existing(db_user) -> None:
    sync_watches_from_config(
        db_user,
        {"defaults": {}, "alerts": [_price_alert("keep", symbol="AAPL")]},
    )
    assert len(list_watches_for_symbol("AAPL")) == 1

    with pytest.raises(InvalidAlertWatchConfig, match="Duplicate alert id"):
        sync_watches_from_config(
            db_user,
            {
                "defaults": {},
                "alerts": [
                    _price_alert("same"),
                    _price_alert("same", symbol="MSFT"),
                ],
            },
        )

    # Failed sync must not wipe the prior watch index.
    assert [w["alert_id"] for w in list_watches_for_symbol("AAPL")] == ["keep"]
