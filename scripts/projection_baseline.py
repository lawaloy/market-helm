#!/usr/bin/env python3
"""Verify or intentionally update the committed projection evaluator baseline."""

from __future__ import annotations

import argparse
from difflib import unified_diff
import json
from pathlib import Path
import sys
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.backtesting import backtest_data_dir  # noqa: E402


BASELINE_DIR = ROOT / "baselines" / "projection-v1"
DATA_DIR = BASELINE_DIR / "data"
REPORT_PATH = BASELINE_DIR / "report.json"


def render_report() -> str:
    """Generate canonical JSON for the committed scenario dataset."""
    report = backtest_data_dir(DATA_DIR, days=3650, max_samples=None)
    return json.dumps(report, indent=2, allow_nan=False, sort_keys=True) + "\n"


def check() -> int:
    """Return nonzero and print a compact diff when the baseline has drifted."""
    actual = render_report()
    try:
        expected = REPORT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Unable to read projection baseline: {exc}", file=sys.stderr)
        return 2
    if actual == expected:
        print("OK: projection evaluator matches baseline v1")
        return 0
    print("Projection evaluator baseline drifted:", file=sys.stderr)
    print(
        "".join(
            unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(REPORT_PATH),
                tofile="generated projection baseline",
            )
        ),
        file=sys.stderr,
        end="",
    )
    return 1


def update() -> int:
    """Rewrite the baseline only through an explicit update command."""
    REPORT_PATH.write_text(render_report(), encoding="utf-8")
    print(f"Updated {REPORT_PATH.relative_to(ROOT).as_posix()}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "update"))
    args = parser.parse_args(argv)
    return update() if args.command == "update" else check()


if __name__ == "__main__":
    raise SystemExit(main())
