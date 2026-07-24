"""Unit tests for SQLite URL resolution and database enablement."""

from pathlib import Path

import pytest

from src.storage.database import (
    database_enabled,
    default_database_path,
    init_database,
    resolve_database_path,
)


class TestDatabaseEnabled:
    def test_disabled_when_unset_or_blank(self, monkeypatch):
        monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
        assert database_enabled() is False

        monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "   ")
        assert database_enabled() is False

    def test_enabled_when_url_present(self, monkeypatch):
        monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite:////tmp/markethelm.db")
        assert database_enabled() is True


class TestResolveDatabasePath:
    def test_missing_url_raises(self, monkeypatch):
        monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="MARKET_HELM_DATABASE_URL is not set"):
            resolve_database_path()

    def test_absolute_sqlite_url(self, monkeypatch, tmp_path):
        db = tmp_path / "markethelm.db"
        monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db.as_posix()}")
        assert resolve_database_path() == Path(db.as_posix())

    def test_four_slash_absolute_url(self, monkeypatch):
        monkeypatch.setenv(
            "MARKET_HELM_DATABASE_URL",
            "sqlite:////var/lib/markethelm/markethelm.db",
        )
        assert resolve_database_path() == Path("/var/lib/markethelm/markethelm.db")

    def test_non_sqlite_scheme_rejected(self, monkeypatch):
        monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "postgres://localhost/db")
        with pytest.raises(ValueError, match="Only sqlite URLs"):
            resolve_database_path()

    def test_sqlite_url_without_path_rejected(self, monkeypatch):
        monkeypatch.setenv("MARKET_HELM_DATABASE_URL", "sqlite://")
        with pytest.raises(ValueError, match="Invalid SQLite URL"):
            resolve_database_path()


class TestInitDatabase:
    def test_init_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
        # Must not raise or create files when multi-user mode is off.
        init_database()

    def test_default_database_path_under_user_config(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "src.storage.database.user_config_dir",
            lambda: tmp_path,
        )
        assert default_database_path() == tmp_path / "markethelm.db"
