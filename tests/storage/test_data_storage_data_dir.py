"""Fetch/CLI writes must land in DATA_DIR so the dashboard and worker can read them."""

from pathlib import Path

from dashboard.backend.services.data_loader import _default_data_dir
from src.storage.data_storage import DataStorage


def test_datastorage_uses_data_dir_env_when_unspecified(monkeypatch, tmp_path):
    target = tmp_path / "persistent-market-data"
    target.mkdir()
    monkeypatch.setenv("DATA_DIR", str(target))

    storage = DataStorage()

    assert storage.data_dir == target


def test_explicit_data_dir_wins_over_env(monkeypatch, tmp_path):
    env_dir = tmp_path / "from-env"
    explicit = tmp_path / "explicit"
    env_dir.mkdir()
    explicit.mkdir()
    monkeypatch.setenv("DATA_DIR", str(env_dir))

    storage = DataStorage(data_dir=str(explicit))

    assert storage.data_dir == explicit


def test_datastorage_defaults_to_local_data_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    storage = DataStorage()

    assert storage.data_dir == Path("data")
    assert (tmp_path / "data").is_dir()


def test_fetch_writes_and_dashboard_reads_the_same_data_dir(monkeypatch, tmp_path):
    target = tmp_path / "var-lib-markethelm-data"
    target.mkdir()
    monkeypatch.setenv("DATA_DIR", str(target))

    storage = DataStorage()
    saved = storage.save_daily_data(
        [{"symbol": "AAPL", "name": "Apple", "close": 150.0}],
    )

    assert saved is not None
    assert Path(saved).parent == target
    assert _default_data_dir() == target.resolve()
    assert list(target.glob("daily_data_*.csv"))
