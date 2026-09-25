"""Hosted watch sync must reject invalid RSI periods and compound shapes."""

import pytest

from src.alerts.alert_rules import MAX_COMPOUND_LEAVES
from src.storage.alert_watches import (
    InvalidAlertWatchConfig,
    list_watches_for_symbol,
    validate_watches_config,
)
from src.storage.database import get_connection, init_database
from src.storage.user_alerts import save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "rsi-compound-watches.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("rsi-watches@example.com", "password123")["id"]


def _rsi_alert(*, period=14, value=30, symbol="AAPL"):
    condition = {
        "type": "rsi_threshold",
        "symbol": symbol,
        "operator": "less_than",
        "value": value,
    }
    if period is not None:
        condition["period"] = period
    return {
        "id": "aapl-rsi",
        "enabled": True,
        "cooldown_minutes": 15,
        "condition": condition,
        "notifications": ["log"],
    }


def _price_leaf(symbol="AAPL", value=150):
    return {
        "type": "price_threshold",
        "symbol": symbol,
        "operator": "less_than",
        "value": value,
    }


def _rsi_leaf(symbol="AAPL", period=14, value=30):
    return {
        "type": "rsi_threshold",
        "symbol": symbol,
        "period": period,
        "operator": "less_than",
        "value": value,
    }


def _compound_alert(*, op="and", leaves=None):
    return {
        "id": "aapl-combo",
        "enabled": True,
        "cooldown_minutes": 15,
        "condition": {
            "type": "compound",
            "op": op,
            "conditions": leaves
            if leaves is not None
            else [_price_leaf(), _rsi_leaf()],
        },
        "notifications": ["log"],
    }


@pytest.mark.parametrize("period", [1, 51, "nope"])
def test_validate_rejects_invalid_rsi_period(db_user, period):
    with pytest.raises(InvalidAlertWatchConfig, match="invalid RSI period"):
        validate_watches_config(
            db_user, {"defaults": {}, "alerts": [_rsi_alert(period=period)]}
        )


def test_validate_accepts_omitted_rsi_period_as_default(db_user):
    validate_watches_config(
        db_user, {"defaults": {}, "alerts": [_rsi_alert(period=None)]}
    )


def test_save_rejects_invalid_rsi_period_without_persisting(db_user):
    with pytest.raises(InvalidAlertWatchConfig, match="invalid RSI period"):
        save_user_alerts_config(
            db_user, {"defaults": {}, "alerts": [_rsi_alert(period=1)]}
        )

    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM alert_watches WHERE user_id = ?",
            (db_user,),
        ).fetchone()["n"]
    assert count == 0


@pytest.mark.parametrize(
    "condition, match",
    [
        (
            {"type": "compound", "op": "xor", "conditions": [_price_leaf()]},
            "op 'and' or 'or'",
        ),
        (
            {"type": "compound", "op": "and", "conditions": []},
            "must include conditions",
        ),
        (
            {
                "type": "compound",
                "op": "and",
                "conditions": [
                    {
                        "type": "compound",
                        "op": "or",
                        "conditions": [_price_leaf()],
                    }
                ],
            },
            "nested compound",
        ),
        (
            {
                "type": "compound",
                "op": "and",
                "conditions": [_price_leaf(value=i) for i in range(MAX_COMPOUND_LEAVES + 1)],
            },
            "exceeds 5 conditions",
        ),
    ],
)
def test_validate_rejects_invalid_compound_shapes(db_user, condition, match):
    alert = _compound_alert()
    alert["condition"] = condition
    with pytest.raises(InvalidAlertWatchConfig, match=match):
        validate_watches_config(db_user, {"defaults": {}, "alerts": [alert]})


def test_save_indexes_single_symbol_compound(db_user):
    save_user_alerts_config(
        db_user, {"defaults": {}, "alerts": [_compound_alert()]}
    )
    watches = list_watches_for_symbol("AAPL")
    assert len(watches) == 1
    assert watches[0]["condition_type"] == "compound"
    assert watches[0]["alert_id"] == "aapl-combo"
