"""get_connection must map parent mkdir OSError to a clear RuntimeError."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage.database import get_connection


def test_get_connection_mkdir_oserror_raises_runtime_error(monkeypatch, tmp_path):
    """Unwritable database parents must fail with an actionable RuntimeError."""
    db = tmp_path / "blocked" / "markethelm.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db.as_posix()}")

    def boom(self, *args, **kwargs):
        raise OSError("read-only filesystem")

    with patch.object(Path, "mkdir", boom):
        with pytest.raises(RuntimeError, match="Cannot create database directory"):
            with get_connection():
                pass


def test_get_connection_mkdir_permission_error_chains_cause(monkeypatch, tmp_path):
    """Permission failures should preserve the original OSError as __cause__."""
    db = tmp_path / "noperm" / "markethelm.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db.as_posix()}")

    def boom(self, *args, **kwargs):
        raise PermissionError("permission denied")

    with patch.object(Path, "mkdir", boom):
        with pytest.raises(RuntimeError) as exc_info:
            with get_connection():
                pass

    assert isinstance(exc_info.value.__cause__, PermissionError)
