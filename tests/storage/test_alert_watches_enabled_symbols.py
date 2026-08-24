"""list_enabled_symbols must drop poison DB tickers so evaluate jobs cannot fan out junk."""

import pytest

from src.storage.alert_watches import (
    list_enabled_symbols,
    list_watches_for_symbol,
    sync_watches_from_config,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "enabled-symbols.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("enabled-symbols@example.com", "password123")["id"]


def _price_config(*symbols_and_ids):
    alerts = [
        {
            "id": alert_id,
            "enabled": True,
            "cooldown_minutes": 0,
            "condition": {
                "type": "price_threshold",
                "symbol": symbol,
                "operator": "less_than",
                "value": 200,
            },
        }
        for symbol, alert_id in symbols_and_ids
    ]
    return {"defaults": {}, "alerts": alerts}


def test_list_watches_for_symbol_rejects_blank_and_sentinel_lookups(db_user) -> None:
    sync_watches_from_config(db_user, _price_config(("AAPL", "aapl-low")))
    assert list_watches_for_symbol("") == []
    assert list_watches_for_symbol("   ") == []
    assert list_watches_for_symbol("nan") == []
    assert list_watches_for_symbol("../ETC/PASSWD") == []
    assert len(list_watches_for_symbol("AAPL")) == 1


@pytest.mark.parametrize("poison", ["NAN", "INF", "../ETC/PASSWD", "AAPL/MSFT"])
def test_list_enabled_symbols_skips_poison_db_tickers(db_user, poison) -> None:
    """SQL still returns the row; normalize_ticker must drop it before evaluate fan-out."""
    sync_watches_from_config(
        db_user,
        _price_config(("AAPL", "aapl-low"), ("MSFT", "msft-low")),
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE alert_watches
            SET symbol = ?
            WHERE user_id = ? AND alert_id = ?
            """,
            (poison, db_user, "aapl-low"),
        )

    assert list_enabled_symbols() == ["MSFT"]
    assert poison not in list_enabled_symbols()
    assert poison.upper() not in list_enabled_symbols()
