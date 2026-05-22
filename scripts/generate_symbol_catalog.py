#!/usr/bin/env python3
"""Write dashboard/frontend/public/symbols-catalog.json from index constituents."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.backend.api.history import build_symbol_catalog  # noqa: E402

OUT = ROOT / "dashboard" / "frontend" / "public" / "symbols-catalog.json"


def main() -> int:
    symbols, names = build_symbol_catalog()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"symbols": symbols, "names": names, "count": len(symbols)}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(symbols)} symbols to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
