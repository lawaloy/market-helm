"""Tests for dashboard alerts settings API."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def alerts_config_dir(tmp_path: Path, monkeypatch):
    """Isolated alerts config directory."""
    config_dir = tmp_path / "market-helm"
    config_dir.mkdir()
    monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_dir / "alerts.json"))
    return config_dir


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


class TestAlertsConfigAPI:
    def test_get_config_when_missing_returns_empty(self, client, alerts_config_dir):
        r = client.get("/api/alerts/config")
        assert r.status_code == 200
        data = r.json()
        assert data["exists"] is False
        assert data["config"]["alerts"] == []

    def test_get_config_never_returns_webhook_url(self, client, alerts_config_dir, monkeypatch):
        config_path = alerts_config_dir / "alerts.json"
        monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_path))
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/secret/token")
        config_path.write_text(
            json.dumps(
                {
                    "defaults": {"webhook_url": "https://discord.com/api/webhooks/leaked/token"},
                    "alerts": [],
                }
            ),
            encoding="utf-8",
        )
        r = client.get("/api/alerts/config")
        assert r.status_code == 200
        data = r.json()
        assert data["config"]["defaults"].get("webhook_url") is None
        assert data["channels"]["webhook_url"] is True
        assert "secret" not in json.dumps(data)

    def test_init_creates_config(self, client, alerts_config_dir):
        r = client.post("/api/alerts/init")
        assert r.status_code == 200
        assert (alerts_config_dir / "alerts.json").exists()

        r2 = client.get("/api/alerts/config")
        assert r2.status_code == 200
        assert r2.json()["exists"] is True
        assert r2.json()["config"]["alerts"] == []

    def test_init_conflict_without_force(self, client, alerts_config_dir):
        path = alerts_config_dir / "alerts.json"
        path.write_text('{"alerts": []}', encoding="utf-8")
        r = client.post("/api/alerts/init")
        assert r.status_code == 409

    def test_put_and_get_config(self, client, alerts_config_dir):
        payload = {
            "defaults": {"email_to": "user@example.com"},
            "alerts": [
                {
                    "id": "aapl_drop",
                    "name": "AAPL drop",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 150,
                    },
                    "notifications": ["log", "email"],
                    "cooldown_minutes": 60,
                }
            ],
        }
        r = client.put("/api/alerts/config", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["exists"] is True
        assert data["config"]["defaults"]["email_to"] == "user@example.com"
        assert data["config"]["alerts"][0]["id"] == "aapl_drop"

        saved = json.loads((alerts_config_dir / "alerts.json").read_text(encoding="utf-8"))
        assert saved["alerts"][0]["enabled"] is True

    def test_put_config_persists_webhook_secret_only_to_user_env(
        self, client, alerts_config_dir, tmp_path, monkeypatch
    ):
        user_config_dir = tmp_path / "user-config"
        monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_config_dir)
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("ALERT_WEBHOOK_FORMAT", raising=False)
        payload = {
            "defaults": {
                "webhook_url": " https://discord.com/api/webhooks/secret/token ",
                "webhook_format": "DISCORD",
            },
            "alerts": [
                {
                    "id": "aapl_drop",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 150,
                    },
                    "notifications": ["webhook"],
                    "webhook_url": "https://discord.com/api/webhooks/rule/secret",
                }
            ],
        }

        r = client.put("/api/alerts/config", json=payload)

        assert r.status_code == 200
        data = r.json()
        serialized_response = json.dumps(data)
        assert "secret/token" not in serialized_response
        assert "rule/secret" not in serialized_response
        assert data["channels"]["webhook_url"] is True
        assert data["config"]["defaults"]["webhook_format"] == "discord"
        assert data["config"]["defaults"].get("webhook_url") is None
        assert "webhook_url" not in data["config"]["alerts"][0]

        saved = json.loads((alerts_config_dir / "alerts.json").read_text(encoding="utf-8"))
        assert saved["defaults"]["webhook_format"] == "discord"
        assert "webhook_url" not in saved["defaults"]
        assert "webhook_url" not in saved["alerts"][0]

        env_file = user_config_dir / ".env"
        assert env_file.read_text(encoding="utf-8").splitlines() == [
            "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/secret/token",
            "ALERT_WEBHOOK_FORMAT=discord",
        ]

    def test_test_alert_dry_run(self, client, alerts_config_dir):
        payload = {
            "defaults": {"email_to": "user@example.com"},
            "alerts": [
                {
                    "id": "test_rule",
                    "name": "Test rule",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 1,
                    },
                    "notifications": ["log"],
                }
            ],
        }
        client.put("/api/alerts/config", json=payload)
        r = client.post("/api/alerts/test", json={"id": "test_rule", "dry_run": True})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "dry_run"
        assert data["notifiers"] == []

    def test_test_alert_not_found(self, client, alerts_config_dir):
        r = client.post("/api/alerts/test", json={"id": "missing", "dry_run": True})
        assert r.status_code == 404

    def test_get_symbols_includes_index_catalog(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.api.alerts.build_symbol_catalog",
            lambda: (["AAPL", "MSFT", "ZZZZ"], {"AAPL": "Apple Inc.", "MSFT": "Microsoft", "ZZZZ": "ZZZZ"}),
        )
        r = client.get("/api/alerts/symbols")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 3
        assert "AAPL" in data["symbols"]
        assert data["names"]["AAPL"] == "Apple Inc."
        assert "prices" in data

    def test_post_quotes(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.api.alerts.resolve_symbol_prices",
            lambda symbols, fetch_missing=True: {"AAPL": 180.0},
        )
        r = client.post("/api/alerts/quotes", json={"symbols": ["AAPL", "MSFT"]})
        assert r.status_code == 200
        assert r.json()["prices"]["AAPL"] == 180.0

    def test_post_quotes_caps_symbols_before_resolving(self, client, monkeypatch):
        captured = {}

        def fake_resolve(symbols, fetch_missing=True):
            captured["symbols"] = symbols
            captured["fetch_missing"] = fetch_missing
            return {}

        monkeypatch.setattr(
            "dashboard.backend.api.alerts.resolve_symbol_prices",
            fake_resolve,
        )

        r = client.post(
            "/api/alerts/quotes",
            json={"symbols": [f"SYM{i}" for i in range(20)]},
        )

        assert r.status_code == 200
        assert captured["symbols"] == [f"SYM{i}" for i in range(15)]
        assert captured["fetch_missing"] is True

    def test_get_quotes(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.api.alerts.resolve_symbol_prices",
            lambda symbols, fetch_missing=True: {"AON": 412.5, "APH": 88.0},
        )
        r = client.get("/api/alerts/quotes", params={"symbols": "AON,APH"})
        assert r.status_code == 200
        assert r.json()["prices"]["AON"] == 412.5

    def test_get_status(self, client, alerts_config_dir, tmp_path, monkeypatch):
        from src.alerts.alert_storage import AlertStorage

        storage = AlertStorage(data_dir=tmp_path)
        storage.record_delivery(
            alert_id="rule1",
            channel="email",
            success=True,
            test=True,
            timestamp="2026-06-21T12:00:00",
        )
        monkeypatch.setattr(
            "src.alerts.alert_storage.AlertStorage",
            lambda data_dir=None: storage,
        )

        r = client.get("/api/alerts/status")
        assert r.status_code == 200
        data = r.json()
        assert data["checks_on_fetch"] is True
        assert "tracked_symbols" in data
        assert "active_watches" in data
        assert data["latest_deliveries"]
        assert data["latest_deliveries"][0]["channel"] == "email"
        assert data["latest_deliveries"][0]["success"] is True

    def test_get_status_preserves_timestamp_when_deliveries_raise(
        self, client, alerts_config_dir, monkeypatch
    ):
        """Delivery channel lookup failure must not wipe last_triggered_at."""

        class PartialStorage:
            def latest_event_timestamp(self):
                return "2026-07-24T10:00:00"

        monkeypatch.setattr(
            "src.alerts.alert_storage.AlertStorage",
            lambda data_dir=None: PartialStorage(),
        )
        monkeypatch.setattr(
            "src.alerts.delivery_status.latest_deliveries_by_channel",
            lambda _storage: (_ for _ in ()).throw(RuntimeError("delivery index corrupt")),
        )

        r = client.get("/api/alerts/status")
        assert r.status_code == 200
        data = r.json()
        assert data["last_triggered_at"] == "2026-07-24T10:00:00"
        assert data["latest_deliveries"] == []

    def test_run_without_config(self, client, alerts_config_dir):
        r = client.post("/api/alerts/run")
        assert r.status_code == 200
        assert r.json()["triggered"] == 0
