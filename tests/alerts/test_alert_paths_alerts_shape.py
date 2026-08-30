"""Truthy non-list alerts.json ``alerts`` keys must soft-fail, not TypeError."""

import json
from pathlib import Path

import pytest

from src.alerts.alert_paths import (
    dedupe_alerts_config,
    get_enabled_watch_symbols,
    polish_alerts_config,
    save_alerts_config,
    strip_webhook_secrets_from_config,
)


@pytest.mark.parametrize("bad_alerts", [1, True, "ab", {"id": "x"}])
def test_polish_tolerates_truthy_non_list_alerts(bad_alerts) -> None:
    """``or []`` still iterates 1/true/dict and aborts Settings GET / file save."""
    polished = polish_alerts_config(
        {"defaults": {"email_to": "ops@example.com"}, "alerts": bad_alerts},
        seed_env_email=False,
    )
    assert polished["defaults"]["email_to"] == "ops@example.com"
    assert polished["alerts"] == []


def test_polish_tolerates_null_alerts() -> None:
    polished = polish_alerts_config(
        {"defaults": {}, "alerts": None},
        seed_env_email=False,
    )
    assert polished["alerts"] == []


@pytest.mark.parametrize("bad_alerts", [1, True, "ab", {"id": "x"}])
def test_strip_webhook_tolerates_truthy_non_list_alerts(bad_alerts) -> None:
    cleaned = strip_webhook_secrets_from_config(
        {
            "defaults": {"webhook_url": "https://hooks.example/secret"},
            "alerts": bad_alerts,
        }
    )
    assert "webhook_url" not in cleaned["defaults"]
    assert cleaned["alerts"] == []


def test_get_enabled_watch_symbols_ignores_non_list_alerts(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = tmp_path / "alerts.json"
    cfg.write_text('{"defaults": {}, "alerts": 1}', encoding="utf-8")
    monkeypatch.setattr(
        "src.alerts.alert_paths.resolve_alerts_config_path",
        lambda explicit=None: cfg,
    )

    assert get_enabled_watch_symbols() == []


@pytest.mark.parametrize("bad_alerts", [1, True, "ab", {"id": "x"}])
def test_dedupe_tolerates_truthy_non_list_alerts(bad_alerts) -> None:
    """Direct dedupe is used by polish; ``or []`` still iterates a truthy non-list."""
    deduped = dedupe_alerts_config(
        {"defaults": {"email_to": "ops@example.com"}, "alerts": bad_alerts}
    )
    assert deduped["defaults"]["email_to"] == "ops@example.com"
    assert deduped["alerts"] == []


def test_save_alerts_config_tolerates_non_list_alerts(tmp_path: Path) -> None:
    dest = tmp_path / "alerts.json"
    save_alerts_config({"defaults": {}, "alerts": 1}, explicit=dest)
    written = json.loads(dest.read_text(encoding="utf-8"))
    assert written["alerts"] == []


def test_polish_preserves_valid_alerts_list() -> None:
    polished = polish_alerts_config(
        {
            "defaults": {},
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
                }
            ],
        },
        seed_env_email=False,
    )
    assert len(polished["alerts"]) == 1
    assert polished["alerts"][0]["id"] == "keep"
