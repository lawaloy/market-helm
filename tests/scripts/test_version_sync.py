"""Regression tests for the release version synchronization helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "version_sync.py"
SPEC = importlib.util.spec_from_file_location("version_sync", MODULE_PATH)
assert SPEC is not None
version_sync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(version_sync)


def _write_repo(root: Path, *, setup_version: str = "1.2.3", dashboard_version: str = "1.2.3") -> None:
    """Create the minimal repo shape that version_sync expects."""
    (root / "dashboard" / "frontend").mkdir(parents=True)
    (root / "dashboard" / "backend").mkdir(parents=True)

    (root / "setup.cfg").write_text(
        f"[metadata]\nname = market-helm\nversion = {setup_version}\n",
        encoding="utf-8",
    )
    (root / "dashboard" / "frontend" / "package.json").write_text(
        json.dumps({"name": "market-helm-web", "version": dashboard_version}) + "\n",
        encoding="utf-8",
    )
    (root / "dashboard" / "frontend" / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "market-helm-web",
                "version": dashboard_version,
                "lockfileVersion": 3,
                "packages": {"": {"name": "market-helm-web", "version": dashboard_version}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "dashboard" / "backend" / "main.py").write_text(
        '''
app = FastAPI(
    title="MarketHelm API",
    description="Market monitoring dashboard API",
    version="1.2.3",
)


async def root():
    return {
        "service": "MarketHelm API",
        "version": "1.2.3",
    }
'''.lstrip(),
        encoding="utf-8",
    )


def test_check_reports_every_dashboard_version_drift(tmp_path: Path) -> None:
    _write_repo(tmp_path, setup_version="2.0.0", dashboard_version="1.0.0")
    main_py = tmp_path / "dashboard" / "backend" / "main.py"
    main_py.write_text(main_py.read_text(encoding="utf-8").replace("1.2.3", "1.0.0"), encoding="utf-8")

    errors = version_sync.check(tmp_path)

    assert errors == [
        "dashboard/frontend/package.json: version is '1.0.0', setup.cfg has '2.0.0'",
        "dashboard/frontend/package-lock.json root version: '1.0.0' != '2.0.0'",
        'dashboard/frontend/package-lock.json packages[""] version: \'1.0.0\' != \'2.0.0\'',
        "dashboard/backend/main.py FastAPI version: '1.0.0' != '2.0.0'",
        "dashboard/backend/main.py root JSON version: '1.0.0' != '2.0.0'",
    ]


def test_cmd_sync_updates_all_dashboard_version_surfaces(tmp_path: Path) -> None:
    _write_repo(tmp_path, setup_version="3.4.5", dashboard_version="0.1.0")
    main_py = tmp_path / "dashboard" / "backend" / "main.py"
    main_py.write_text(main_py.read_text(encoding="utf-8").replace("1.2.3", "0.1.0"), encoding="utf-8")

    assert version_sync.cmd_sync(tmp_path) == 0

    package_json = json.loads((tmp_path / "dashboard" / "frontend" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (tmp_path / "dashboard" / "frontend" / "package-lock.json").read_text(encoding="utf-8")
    )
    assert package_json["version"] == "3.4.5"
    assert package_lock["version"] == "3.4.5"
    assert package_lock["packages"][""]["version"] == "3.4.5"
    assert version_sync.read_main_py_versions(main_py) == ("3.4.5", "3.4.5")
    assert version_sync.check(tmp_path) == []


def test_sync_main_py_rejects_missing_root_json_marker(tmp_path: Path) -> None:
    _write_repo(tmp_path, setup_version="9.9.9")
    main_py = tmp_path / "dashboard" / "backend" / "main.py"
    before_sync = main_py.read_text(encoding="utf-8").replace(
        '"service": "MarketHelm API",',
        '"service": "Other API",',
    )
    main_py.write_text(before_sync, encoding="utf-8")

    error = version_sync.sync_main_py(main_py, "9.9.9")

    assert error is not None
    assert "Could not find the root JSON version" in error
    assert main_py.read_text(encoding="utf-8") == before_sync
    assert version_sync.read_main_py_versions(main_py) == (None, None)
