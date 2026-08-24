"""DataStorage must fail loud when the data directory cannot be created."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage.data_storage import DataStorage


def test_init_mkdir_oserror_raises(tmp_path):
    """Unwritable data roots must not swallow the OSError and continue."""

    def boom(self, *args, **kwargs):
        raise OSError("read-only filesystem")

    with patch.object(Path, "mkdir", boom):
        with pytest.raises(OSError, match="read-only filesystem"):
            DataStorage(data_dir=str(tmp_path / "blocked"))
