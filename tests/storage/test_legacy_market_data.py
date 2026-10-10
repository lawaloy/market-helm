"""Legacy CSV/JSON backfill into the durable market-data store."""

from __future__ import annotations

import json

from src.storage.legacy_market_data import backfill_legacy_market_data
from src.storage.market_bars import load_market_bars, upsert_market_bars
from src.storage.projections_store import (
    load_daily_summary,
    load_projections,
    upsert_daily_summary,
    upsert_projections,
)


def _write_legacy_set(data_dir, day="2026-09-18", close=150.0):
    (data_dir / f"daily_data_{day}.csv").write_text(
        "\ufeffsymbol,name,close,volume\n" f"AAPL,Apple,{close},1000\n" "BAD,Bad,NaN,1\n",
        encoding="utf-8",
    )
    (data_dir / f"projections_{day}.csv").write_text(
        "symbol,current_price,target_mid,confidence\n" f"AAPL,{close},{close + 5},80\n" ",1,2,3\n",
        encoding="utf-8",
    )
    (data_dir / f"summary_{day}.json").write_text(
        json.dumps(
            {
                "analysis": {"total_stocks": 1},
                "projections": {"AAPL": {"symbol": "AAPL"}},
            }
        ),
        encoding="utf-8",
    )


def test_backfill_imports_all_legacy_stores(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    _write_legacy_set(tmp_path)

    report = backfill_legacy_market_data(tmp_path)

    assert report["errors"] == []
    assert report["target"] == str(tmp_path / "market_bars.sqlite")
    assert report["daily_data"] == {
        "discovered_files": 1,
        "imported_files": 1,
        "skipped_existing_files": 0,
        "rows_written": 1,
        "invalid_rows": 1,
    }
    assert report["projections"]["rows_written"] == 1
    assert report["projections"]["invalid_rows"] == 1
    assert report["projections"]["embedded_summary_fallbacks"] == 0
    assert report["summaries"]["rows_written"] == 1

    bars = load_market_bars("2026-09-18", data_dir=tmp_path)
    assert [(row["symbol"], row["close"], row["source"]) for row in bars] == [
        ("AAPL", 150.0, "legacy_csv")
    ]
    projections = load_projections("2026-09-18", data_dir=tmp_path)
    assert projections[0]["target_mid"] == 155.0
    assert projections[0]["source"] == "legacy_csv"
    summary = load_daily_summary("2026-09-18", data_dir=tmp_path)
    assert summary["analysis"] == {"total_stocks": 1}
    assert "projections" not in summary


def test_backfill_is_idempotent_and_preserves_existing_dates(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    _write_legacy_set(tmp_path, close=150.0)
    first = backfill_legacy_market_data(tmp_path)
    assert first["errors"] == []

    _write_legacy_set(tmp_path, close=999.0)
    second = backfill_legacy_market_data(tmp_path)

    assert second["daily_data"]["skipped_existing_files"] == 1
    assert second["projections"]["skipped_existing_files"] == 1
    assert second["summaries"]["skipped_existing_files"] == 1
    assert load_market_bars("2026-09-18", data_dir=tmp_path)[0]["close"] == 150.0


def test_backfill_can_explicitly_replace_existing_dates(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    upsert_market_bars([{"symbol": "AAPL", "close": 10.0}], "2026-09-18", data_dir=tmp_path)
    _write_legacy_set(tmp_path, close=175.0)

    report = backfill_legacy_market_data(tmp_path, replace_existing=True)

    assert report["errors"] == []
    assert load_market_bars("2026-09-18", data_dir=tmp_path)[0]["close"] == 175.0


def test_backfill_continues_after_malformed_sibling_file(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    (tmp_path / "daily_data_2026-09-18.csv").write_text(
        "symbol,close\nAAPL,150\n", encoding="utf-8"
    )
    (tmp_path / "summary_2026-09-18.json").write_text("{not-json", encoding="utf-8")
    (tmp_path / "daily_data_2026-99-99.csv").write_text("symbol,close\nBAD,1\n", encoding="utf-8")

    report = backfill_legacy_market_data(tmp_path)

    assert report["daily_data"]["imported_files"] == 1
    assert report["summaries"]["imported_files"] == 0
    assert report["errors"][0]["file"] == "summary_2026-09-18.json"
    assert [row["symbol"] for row in load_market_bars("2026-09-18", data_dir=tmp_path)] == ["AAPL"]


def test_backfill_empty_directory_does_not_create_sidecar(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)

    report = backfill_legacy_market_data(tmp_path)

    assert report["errors"] == []
    assert not (tmp_path / "market_bars.sqlite").exists()


def test_backfill_reports_configured_database_target(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:///unused.sqlite")

    report = backfill_legacy_market_data(tmp_path)

    assert report["target"] == "configured_database"
    assert not (tmp_path / "market_bars.sqlite").exists()


def test_backfill_recovers_projections_embedded_in_summary(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    (tmp_path / "summary_2026-09-18.json").write_text(
        json.dumps(
            {
                "analysis": {"total_stocks": 1},
                "projections": {
                    "AAPL": {
                        "symbol": "AAPL",
                        "current_price": 150,
                        "target_mid": 155,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    report = backfill_legacy_market_data(tmp_path)

    assert report["errors"] == []
    assert report["projections"]["embedded_summary_fallbacks"] == 1
    assert report["projections"]["rows_written"] == 1
    assert load_projections("2026-09-18", data_dir=tmp_path)[0]["source"] == ("legacy_summary")


def test_backfill_uses_summary_fallback_after_malformed_projection_csv(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    (tmp_path / "projections_2026-09-18.csv").write_text("", encoding="utf-8")
    (tmp_path / "summary_2026-09-18.json").write_text(
        json.dumps({"projections": {"AAPL": {"symbol": "AAPL"}}}),
        encoding="utf-8",
    )

    report = backfill_legacy_market_data(tmp_path)

    assert report["errors"][0]["file"] == "projections_2026-09-18.csv"
    assert report["projections"]["embedded_summary_fallbacks"] == 1
    assert [row["symbol"] for row in load_projections("2026-09-18", data_dir=tmp_path)] == ["AAPL"]


def test_backfill_recovers_embedded_projections_when_summary_already_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    upsert_daily_summary({"analysis": {"total_stocks": 1}}, "2026-09-18", data_dir=tmp_path)
    (tmp_path / "summary_2026-09-18.json").write_text(
        json.dumps({"projections": {"AAPL": {"symbol": "AAPL"}}}),
        encoding="utf-8",
    )

    report = backfill_legacy_market_data(tmp_path)

    assert report["summaries"]["skipped_existing_files"] == 1
    assert report["projections"]["embedded_summary_fallbacks"] == 1
    assert [row["symbol"] for row in load_projections("2026-09-18", data_dir=tmp_path)] == ["AAPL"]


def test_replace_existing_uses_embedded_projections_without_csv(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    upsert_projections(
        [{"symbol": "AAPL", "target_mid": 100}],
        "2026-09-18",
        data_dir=tmp_path,
    )
    (tmp_path / "summary_2026-09-18.json").write_text(
        json.dumps({"projections": {"AAPL": {"symbol": "AAPL", "target_mid": 200}}}),
        encoding="utf-8",
    )

    report = backfill_legacy_market_data(tmp_path, replace_existing=True)

    assert report["errors"] == []
    assert report["projections"]["embedded_summary_fallbacks"] == 1
    assert load_projections("2026-09-18", data_dir=tmp_path)[0]["target_mid"] == 200


def test_replace_existing_prefers_valid_projection_csv_over_summary(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    (tmp_path / "projections_2026-09-18.csv").write_text(
        "symbol,target_mid\nAAPL,175\n", encoding="utf-8"
    )
    (tmp_path / "summary_2026-09-18.json").write_text(
        json.dumps({"projections": {"AAPL": {"symbol": "AAPL", "target_mid": 999}}}),
        encoding="utf-8",
    )

    report = backfill_legacy_market_data(tmp_path, replace_existing=True)

    assert report["errors"] == []
    assert report["projections"]["embedded_summary_fallbacks"] == 0
    assert load_projections("2026-09-18", data_dir=tmp_path)[0]["target_mid"] == 175
