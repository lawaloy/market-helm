"""Make the repository root importable for scripts run as ``python scripts/<name>.py``.

Importing this module (before any ``src`` / ``scripts`` imports) puts the repo root on
``sys.path``. It replaces the ``sys.path.insert`` preamble the scripts used to carry
inline, so their repo-dependent imports can sit at the top of the file and still fail
fast at startup.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
