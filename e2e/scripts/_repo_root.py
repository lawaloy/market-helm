"""Put the repository root on ``sys.path`` for scripts run as ``python e2e/scripts/<name>.py``.

Import this module before any ``src`` / ``dashboard`` imports.
"""

import sys
from pathlib import Path

# Repo root (e2e/scripts -> parents[2])
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
