"""Corrupt alerts.json and non-dict alert rows must soft-fail, not raise."""

import json
from pathlib import Path

from src.alerts.alert_paths import (
    get_enabled_watch_symbols,
    load_alerts_config,
    polish_alerts_config,
    strip_webhook_secrets_from_config,
)


def test_load_alerts_config_returns_none_for_corrupt_json(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = tmp_path / "alerts.json"
    cfg.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        "src.alerts.alert_paths.resolve_alerts_config_path",
        lambda explicit=None: cfg,
    )

    path, data = load_alerts_config()
    assert path == cfg
    assert data is None


def test_load_alerts_config_returns_none_for_non_object_json(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = tmp_path / "alerts.json"
    cfg.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    monkeypatch.setattr(
        "src.alerts.alert_paths.resolve_alerts_config_path",
        lambda explicit=None: cfg,
    )

    path, data = load_alerts_config()
    assert path == cfg
    assert data is None


def test_polish_skips_non_dict_alert_entries() -> None:
    polished = polish_alerts_config(
        {
            "defaults": {},
            "alerts": [
                "junk",
                None,
                1,
                {
                    "id": "keep",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": ">",
                        "value": 100,
                    },
                },
            ],
        }
    )
    assert len(polished["alerts"]) == 1
    assert polished["alerts"][0]["id"] == "keep"


def test_strip_webhook_secrets_skips_non_dict_alerts() -> None:
    cleaned = strip_webhook_secrets_from_config(
        {
            "defaults": {"webhook_url": "https://secret.example/hook"},
            "alerts": [
                "junk",
                {"id": "a1", "webhook_url": "https://secret.example/a1"},
            ],
        }
    )
    assert "webhook_url" not in cleaned["defaults"]
    assert cleaned["alerts"] == [{"id": "a1"}]


def test_get_enabled_watch_symbols_ignores_non_dict_rows(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = tmp_path / "alerts.json"
    cfg.write_text(
        json.dumps(
            {
                "defaults": {},
                "alerts": [
                    "junk",
                    {
                        "id": "a1",
                        "enabled": True,
                        "condition": {
                            "type": "price_threshold",
                            "symbol": " MSFT ",
                            "operator": "<",
                            "value": 50,
                        },
                    },
                    {
                        "id": "a2",
                        "enabled": True,
                        "condition": "not-a-dict",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.alerts.alert_paths.resolve_alerts_config_path",
        lambda explicit=None: cfg,
    )

    assert get_enabled_watch_symbols() == ["MSFT"]
