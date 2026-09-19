"""Unit coverage for scripts/check_worker_health.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    path = REPO_ROOT / "scripts" / "check_worker_health.py"
    spec = importlib.util.spec_from_file_location("check_worker_health", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_worker_health_requires_ok(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "_fetch", lambda url, timeout: {"ok": False, "worker_id": "w1"})
    assert module.main([]) == 1


def test_check_worker_health_prints_worker_id(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module, "_fetch", lambda url, timeout: {"ok": True, "worker_id": "worker-42"}
    )
    assert module.main(["--print-worker-id"]) == 0
    assert capsys.readouterr().out.strip() == "worker-42"


def test_check_worker_health_requires_new_worker_id(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module, "_fetch", lambda url, timeout: {"ok": True, "worker_id": "worker-1"}
    )
    assert module.main(["--previous-worker-id", "worker-1"]) == 1
    assert module.main(["--previous-worker-id", "worker-0"]) == 0


def test_check_worker_health_handles_network_errors(monkeypatch):
    module = _load_module()

    def boom(url, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(module, "_fetch", boom)
    assert module.main([]) == 1
