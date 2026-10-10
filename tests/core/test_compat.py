"""Backward compatibility for the market-helm -> markethelm rename."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.core import compat


@pytest.fixture(autouse=True)
def _reset_warned(monkeypatch):
    monkeypatch.setattr(compat, "_warned", set())


def test_new_env_name_is_used(monkeypatch):
    monkeypatch.setenv("MARKETHELM_DATABASE_URL", "sqlite:///new.db")
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    assert compat.get_env("MARKETHELM_DATABASE_URL") == "sqlite:///new.db"


def test_deprecated_env_name_is_honoured_with_one_warning(monkeypatch, caplog):
    monkeypatch.delenv("MARKETHELM_AUTH_SECRET", raising=False)
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "legacy-secret-value")
    with caplog.at_level(logging.WARNING, logger=compat.__name__):
        assert compat.get_env("MARKETHELM_AUTH_SECRET") == "legacy-secret-value"
        assert compat.get_env("MARKETHELM_AUTH_SECRET") == "legacy-secret-value"
    warnings = [r for r in caplog.records if "deprecated" in r.getMessage()]
    assert len(warnings) == 1
    assert "MARKET_HELM_AUTH_SECRET" in warnings[0].getMessage()
    assert "MARKETHELM_AUTH_SECRET" in warnings[0].getMessage()


def test_new_env_name_takes_precedence(monkeypatch, caplog):
    monkeypatch.setenv("MARKETHELM_PUBLIC_URL", "https://new.example")
    monkeypatch.setenv("MARKET_HELM_PUBLIC_URL", "https://old.example")
    with caplog.at_level(logging.WARNING, logger=compat.__name__):
        assert compat.get_env("MARKETHELM_PUBLIC_URL") == "https://new.example"
    assert not caplog.records


def test_empty_new_value_falls_back_to_deprecated_name(monkeypatch):
    monkeypatch.setenv("MARKETHELM_PORT", "")
    monkeypatch.setenv("MARKET_HELM_PORT", "9000")
    assert compat.get_env("MARKETHELM_PORT") == "9000"


def test_default_and_unset(monkeypatch):
    monkeypatch.delenv("MARKETHELM_PORT", raising=False)
    monkeypatch.delenv("MARKET_HELM_PORT", raising=False)
    assert compat.get_env("MARKETHELM_PORT") is None
    assert compat.get_env("MARKETHELM_PORT", "8000") == "8000"


def test_non_prefixed_names_have_no_legacy_alias():
    assert compat.legacy_env_name("FINNHUB_API_KEY") is None
    assert compat.legacy_env_name("MARKETHELM_X") == "MARKET_HELM_X"


def test_user_dir_prefers_new_and_leaves_legacy_alone(tmp_path: Path):
    (tmp_path / ".markethelm").mkdir()
    (tmp_path / ".market-helm").mkdir()
    assert compat.resolve_user_config_dir(tmp_path) == tmp_path / ".markethelm"
    assert (tmp_path / ".market-helm").exists()


def test_user_dir_migrates_market_helm(tmp_path: Path):
    legacy = tmp_path / ".market-helm"
    legacy.mkdir()
    (legacy / "alerts.json").write_text("{}", encoding="utf-8")
    resolved = compat.resolve_user_config_dir(tmp_path)
    assert resolved == tmp_path / ".markethelm"
    assert (resolved / "alerts.json").read_text(encoding="utf-8") == "{}"
    assert not legacy.exists()


def test_user_dir_migrates_market_desk(tmp_path: Path):
    (tmp_path / ".market-desk").mkdir()
    assert compat.resolve_user_config_dir(tmp_path) == tmp_path / ".markethelm"
    assert not (tmp_path / ".market-desk").exists()


def test_user_dir_keeps_legacy_when_rename_fails(monkeypatch, tmp_path: Path):
    legacy = tmp_path / ".market-helm"
    legacy.mkdir()

    def boom(self, target):
        raise OSError("in use")

    monkeypatch.setattr(Path, "rename", boom)
    assert compat.resolve_user_config_dir(tmp_path) == legacy


def test_user_dir_defaults_to_new_when_nothing_exists(tmp_path: Path):
    assert compat.resolve_user_config_dir(tmp_path) == tmp_path / ".markethelm"
