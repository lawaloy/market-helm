"""Direct projections/summary store validation after the #639 CSV/JSON cutover."""

from datetime import date

import pytest

from src.storage.market_bars import market_bars_connection
from src.storage.projections_store import (
    list_projection_dates,
    list_summary_dates,
    load_daily_summary,
    load_projections,
    upsert_daily_summary,
    upsert_projections,
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    return tmp_path


def test_upsert_projections_rejects_invalid_run_date(data_dir):
    with pytest.raises(ValueError, match="Invalid run_date"):
        upsert_projections(
            [{"symbol": "AAPL", "current_price": 10.0}],
            "not-a-date",
            data_dir=data_dir,
        )


def test_upsert_projections_skips_blank_symbols_and_non_dicts(data_dir):
    written = upsert_projections(
        [
            "skip-me",
            {"symbol": "   ", "current_price": 10.0},
            {
                "symbol": "aapl",
                "name": "Apple",
                "current_price": float("inf"),
                "confidence": float("nan"),
                "projection_horizon_sessions": "nope",
                "target_mid": 155.0,
            },
        ],
        date(2026, 9, 18),
        data_dir=data_dir,
    )
    assert written == 1
    rows = load_projections("2026-09-18", data_dir=data_dir)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["current_price"] is None
    assert rows[0]["confidence"] is None
    assert rows[0]["projection_horizon_sessions"] is None
    assert rows[0]["target_mid"] == 155.0
    assert load_projections("not-a-date", data_dir=data_dir) == []


def test_list_projection_dates_clamps_invalid_limits(data_dir):
    upsert_projections(
        [{"symbol": "AAPL", "current_price": 10.0}],
        "2026-09-18",
        data_dir=data_dir,
    )
    assert list_projection_dates(data_dir=data_dir, limit=0) == []
    assert list_projection_dates(data_dir=data_dir, limit="nope") == ["2026-09-18"]


def test_upsert_daily_summary_drops_nested_projections(data_dir):
    location = upsert_daily_summary(
        {
            "ai_summary": 42,
            "analysis": {"total_stocks": 2},
            "exchange_comparison": "not-a-dict",
            "projections": {"AAPL": {"symbol": "AAPL"}},
            "keep": True,
        },
        "2026-09-18",
        data_dir=data_dir,
    )
    assert location == "summary:2026-09-18"
    loaded = load_daily_summary("2026-09-18", data_dir=data_dir)
    # Payload JSON keeps the original ai_summary type; the column is stringified
    # so a later poison-payload rebuild can still recover text.
    assert loaded["ai_summary"] == 42
    assert loaded["analysis"] == {"total_stocks": 2}
    assert "projections" not in loaded
    assert loaded["keep"] is True
    with market_bars_connection(data_dir=data_dir) as conn:
        row = conn.execute(
            "SELECT ai_summary, exchange_comparison_json FROM daily_summaries "
            "WHERE summary_date = ?",
            ("2026-09-18",),
        ).fetchone()
    assert row["ai_summary"] == "42"
    assert row["exchange_comparison_json"] == "{}"
    assert list_summary_dates(data_dir=data_dir, limit=-1) == []
    assert load_daily_summary("not-a-date", data_dir=data_dir) is None


def test_load_daily_summary_rebuilds_from_columns_when_payload_is_poison(data_dir):
    upsert_daily_summary(
        {
            "ai_summary": "ok",
            "analysis": {"total_stocks": 3},
            "exchange_comparison": {"nasdaq": 1},
            "projection_summary": {"count": 4},
        },
        "2026-09-19",
        data_dir=data_dir,
    )
    with market_bars_connection(data_dir=data_dir) as conn:
        conn.execute(
            "UPDATE daily_summaries SET payload_json = ? WHERE summary_date = ?",
            ("not-json", "2026-09-19"),
        )

    loaded = load_daily_summary("2026-09-19", data_dir=data_dir)
    assert loaded["date"] == "2026-09-19"
    assert loaded["ai_summary"] == "ok"
    assert loaded["analysis"] == {"total_stocks": 3}
    assert loaded["exchange_comparison"] == {"nasdaq": 1}
    assert loaded["projection_summary"] == {"count": 4}


def test_load_daily_summary_backfills_missing_keys_from_columns(data_dir):
    """Partial payload_json must keep present keys and fill missing ones from columns."""
    upsert_daily_summary(
        {
            "ai_summary": "column text",
            "analysis": {"total_stocks": 5},
            "exchange_comparison": {"nasdaq": 2},
            "projection_summary": {"count": 7},
        },
        "2026-09-20",
        data_dir=data_dir,
    )
    with market_bars_connection(data_dir=data_dir) as conn:
        conn.execute(
            "UPDATE daily_summaries SET payload_json = ? WHERE summary_date = ?",
            (
                '{"date": "2026-09-20", "keep": true, "analysis": {"stale": 1}}',
                "2026-09-20",
            ),
        )

    loaded = load_daily_summary("2026-09-20", data_dir=data_dir)
    assert loaded["keep"] is True
    assert loaded["date"] == "2026-09-20"
    # A present analysis key is forward-compat payload, not overwritten.
    assert loaded["analysis"] == {"stale": 1}
    assert loaded["exchange_comparison"] == {"nasdaq": 2}
    assert loaded["projection_summary"] == {"count": 7}
    assert loaded["ai_summary"] == "column text"
