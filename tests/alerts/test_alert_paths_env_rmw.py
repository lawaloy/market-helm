"""Regression: concurrent file-mode .env writers must not drop keys."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.alerts.alert_paths import update_user_env_vars


def test_concurrent_update_user_env_vars_preserves_all_keys(
    tmp_path: Path, monkeypatch
) -> None:
    """Two racing updates for distinct keys keep both after unlock."""
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text("SHARED_KEEP=1\n", encoding="utf-8")
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    barrier = threading.Barrier(2)
    n = 40

    def writer(key: str) -> None:
        barrier.wait(timeout=5)
        for index in range(n):
            update_user_env_vars({key: f"{key}-value-{index}"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(writer, "DISCORD_WEBHOOK_URL"),
            pool.submit(writer, "ALERT_EMAIL_TO"),
        ]
        for future in futures:
            future.result(timeout=30)

    lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if "=" in line
    }
    assert lines["SHARED_KEEP"] == "1"
    assert lines["DISCORD_WEBHOOK_URL"] == "DISCORD_WEBHOOK_URL-value-39"
    assert lines["ALERT_EMAIL_TO"] == "ALERT_EMAIL_TO-value-39"


def test_update_user_env_vars_atomic_replace_leaves_no_tmp(
    tmp_path: Path, monkeypatch
) -> None:
    user_dir = tmp_path / ".market-helm"
    env_file = user_dir / ".env"
    user_dir.mkdir()
    env_file.write_text("ALERT_EMAIL_TO=old@example.com\n", encoding="utf-8")
    monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_dir)

    update_user_env_vars({"ALERT_EMAIL_TO": "new@example.com"})

    assert env_file.read_text(encoding="utf-8") == "ALERT_EMAIL_TO=new@example.com\n"
    assert not (user_dir / ".env.tmp").exists()
    assert list(user_dir.glob("*.tmp")) == []
