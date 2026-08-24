"""AlertStorage must fail loud when the history directory cannot be created."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.alerts.alert_storage import AlertStorage


def test_init_mkdir_oserror_raises(tmp_path):
    """Unwritable history roots must not swallow the OSError and continue."""

    def boom(self, *args, **kwargs):
        raise OSError("read-only filesystem")

    with patch.object(Path, "mkdir", boom):
        with pytest.raises(OSError, match="read-only filesystem"):
            AlertStorage(data_dir=tmp_path / "blocked")
