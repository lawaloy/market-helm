#!/usr/bin/env python3
"""Fail unless a trade date is present in market_bars under ``--data-dir``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.market_bars import list_market_bar_dates  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-date", required=True, help="YYYY-MM-DD expected in market_bars")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)

    dates = list_market_bar_dates(data_dir=args.data_dir, limit=args.limit)
    if args.trade_date not in dates:
        print(
            f"Expected trade date {args.trade_date!r} in market_bars; found {dates!r}",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {args.trade_date} present in market_bars ({len(dates)} recent dates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
