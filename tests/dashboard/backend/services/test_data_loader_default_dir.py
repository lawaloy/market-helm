"""Tests for DataLoader DATA_DIR / install-path resolution."""

from pathlib import Path

from dashboard.backend.services import data_loader


def test_default_data_dir_uses_data_dir_env(monkeypatch, tmp_path):
    target = tmp_path / "custom-data"
    target.mkdir()
    monkeypatch.setenv("DATA_DIR", str(target))

    assert data_loader._default_data_dir() == target.resolve()


def test_default_data_dir_uses_user_config_when_installed_in_site_packages(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("DATA_DIR", raising=False)
    fake_module = (
        tmp_path
        / "lib"
        / "python3.12"
        / "site-packages"
        / "dashboard"
        / "backend"
        / "services"
        / "data_loader.py"
    )
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# stub\n", encoding="utf-8")
    user_dir = tmp_path / ".market-helm"
    user_dir.mkdir()

    monkeypatch.setattr(data_loader, "__file__", str(fake_module))
    monkeypatch.setattr(
        "dashboard.backend.user_paths.user_config_dir",
        lambda: user_dir,
    )

    assert data_loader._default_data_dir() == user_dir / "data"


def test_default_data_dir_uses_repo_data_when_developing(monkeypatch, tmp_path):
    monkeypatch.delenv("DATA_DIR", raising=False)
    # Mirror real layout: <root>/dashboard/backend/services/data_loader.py
    fake_module = (
        tmp_path / "dashboard" / "backend" / "services" / "data_loader.py"
    )
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# stub\n", encoding="utf-8")

    monkeypatch.setattr(data_loader, "__file__", str(fake_module))

    assert data_loader._default_data_dir() == tmp_path / "data"
