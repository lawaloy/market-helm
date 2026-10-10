"""Process bootstrap for the dashboard backend, imported before anything else.

Order matters and is preserved from the original ``main.py`` preamble:

1. configure logging so import-time log records use the dashboard format;
2. make the repo root importable when running from a source checkout (so ``src``
   and ``dashboard`` resolve, including ``python main.py`` inside ``backend/``);
3. load ``.env`` files (cwd, repo root, then ``~/.markethelm/.env``) so modules that
   read environment variables at import time see them.
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

_here = Path(__file__).resolve()
REPO_ROOT = None
for _p in _here.parents:
    if (_p / "main.py").is_file() and (_p / "src").is_dir():
        REPO_ROOT = _p
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

try:
    from dotenv import load_dotenv

    load_dotenv()
    for _p in _here.parents:
        if (_p / "main.py").is_file() and (_p / ".env").is_file():
            load_dotenv(_p / ".env")
            break
    _user_env = Path.home() / ".markethelm" / ".env"
    if _user_env.is_file():
        load_dotenv(_user_env, override=True)
except ImportError:
    pass
