"""
MarketHelm — main entry point (convenience wrapper for the CLI).

This is a convenience wrapper for the CLI interface.
- CLI presentation: src/cli/commands.py
- Core workflow logic: src/workflows/tracker.py

You can also run directly:
  python -m src.cli.commands     # CLI interface
  python -m src.workflows.tracker  # Direct workflow (programmatic)
"""

import sys
from pathlib import Path

# Add parent directory to path to enable absolute imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.cli.commands import main

if __name__ == "__main__":
    raise SystemExit(main())
