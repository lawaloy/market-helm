#!/usr/bin/env python3
"""Write dashboard/frontend/public/symbols-catalog.json from index constituents."""

import json

try:
    from scripts import _repo_path
except ImportError:  # run as ``python scripts/<name>.py``: repo root not on sys.path yet
    import _repo_path

from dashboard.backend.api.history import build_symbol_catalog

ROOT = _repo_path.ROOT

OUT = ROOT / "dashboard" / "frontend" / "public" / "symbols-catalog.json"


def main() -> int:
    symbols, names = build_symbol_catalog()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"symbols": symbols, "names": names, "count": len(symbols)}, separators=(",", ":")
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(symbols)} symbols to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
