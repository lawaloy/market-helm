"""File-mode Helmtower status/run/test must survive poison alerts.json.

#552 locks Settings GET/init. Hosted poison-row run/test is locked in
``test_alerts_corrupt_config_recovery``. File-mode Check-now goes through
``AlertEngine.from_config`` (its own json.load), status through
``load_alerts_config``, and Send-test through ``run_alert_test``. A later
``json.loads`` without those soft-fails would 500 the dashboard or map
corrupt files to the missing-config 404.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


POISON_BLOBS = (
    b'{"not": "recoverable"',
    b"[]",
    b'"just-a-string"',
    b"null",
    b"\xff\xfe",
)


@pytest.fixture
def file_mode(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("ALERT_WEBHOOK_FORMAT", raising=False)
    user_dir = tmp_path / "market-helm"
    user_dir.mkdir()
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)
    config_path = user_dir / "alerts.json"
    monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_path))
    return config_path


@pytest.fixture
def client():
    from dashboard.backend.main import app

    return TestClient(app)


def _stub_status_deps(monkeypatch) -> None:
    monkeypatch.setattr(
        "dashboard.backend.api.alerts.database_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "dashboard.backend.api.alerts.get_data_loader",
        lambda: MagicMock(
            get_latest_date=MagicMock(return_value=None),
            load_projections=MagicMock(return_value=MagicMock(empty=True)),
        ),
    )
    monkeypatch.setattr(
        "src.alerts.alert_storage.AlertStorage",
        lambda data_dir=None: MagicMock(
            latest_event_timestamp=MagicMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        "src.alerts.delivery_status.latest_deliveries_by_channel",
        lambda storage: [],
    )


@pytest.mark.parametrize("blob", POISON_BLOBS)
def test_file_mode_status_soft_fails_corrupt_or_non_object_root(
    client, file_mode: Path, blob: bytes, monkeypatch
) -> None:
    """Helmtower status poll must 200 with zero watches, not 500."""
    file_mode.write_bytes(blob)
    _stub_status_deps(monkeypatch)

    response = client.get("/api/alerts/status")
    assert response.status_code == 200
    assert response.json()["active_watches"] == 0
    assert file_mode.read_bytes() == blob


@pytest.mark.parametrize("blob", POISON_BLOBS)
def test_file_mode_run_idles_on_corrupt_or_non_object_root(
    client, file_mode: Path, blob: bytes, monkeypatch
) -> None:
    """Check-now must 200 idle, not 500 or 404 no-market-data."""
    file_mode.write_bytes(blob)

    def _boom_loader():
        raise AssertionError("corrupt config must not load market data")

    monkeypatch.setattr(
        "dashboard.backend.services.data_loader.get_data_loader",
        _boom_loader,
    )

    response = client.post("/api/alerts/run")
    assert response.status_code == 200
    body = response.json()
    assert body["triggered"] == 0
    assert body["message"] == "No active watches configured."
    assert file_mode.read_bytes() == blob


def test_file_mode_test_404s_on_corrupt_without_building_notifiers(
    client, file_mode: Path
) -> None:
    """Send-test must 404 as corrupt (not missing) and skip notifier setup."""
    file_mode.write_text("{not-json", encoding="utf-8")

    with patch(
        "src.cli.alerts_commands.AlertEngine._build_notifiers",
    ) as mock_build:
        response = client.post(
            "/api/alerts/test",
            json={"id": "any", "dry_run": True},
        )

    assert response.status_code == 404
    assert "Corrupt or invalid alerts config" in response.json()["detail"]
    mock_build.assert_not_called()
    assert file_mode.read_text(encoding="utf-8") == "{not-json"
