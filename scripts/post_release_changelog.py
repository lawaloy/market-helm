#!/usr/bin/env python3
"""
Insert a dated release section into CHANGELOG.md after [Unreleased] (Keep a Changelog style).

Idempotent: if ``## [X.Y.Z]`` already exists, exits 0 without changes.
Used by the post-release GitHub Actions job only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def insert_section(text: str, version: str, date: str) -> str | None:
    """
    Return new file contents, or None if no change (section already present).
    """
    if re.search(rf"^## \[{re.escape(version)}\]\s", text, flags=re.MULTILINE):
        return None

    if "## [Unreleased]" not in text:
        print("post_release_changelog: no ## [Unreleased] heading found", file=sys.stderr)
        sys.exit(2)

    unreleased = "## [Unreleased]"
    start = text.index(unreleased)
    rest = text[start:]
    # First versioned heading after [Unreleased]
    m = re.search(r"\n## \[(?!Unreleased)[^\]]+\]", rest)
    insert_at = start + m.start() if m else len(text)

    block = (
        f"\n## [{version}] - {date}\n\n"
        "### Changed\n\n"
        f"- Repository version metadata aligned with Git tag **`v{version}`** / "
        f"PyPI **`{version}`** (automated post-release sync).\n\n"
    )
    return text[:insert_at] + block + text[insert_at:]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", required=True, help="Semver without v prefix, e.g. 0.10.0")
    p.add_argument("--date", required=True, help="ISO date YYYY-MM-DD")
    args = p.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        print("post_release_changelog: version must be MAJOR.MINOR.PATCH", file=sys.stderr)
        return 2

    path = repo_root() / "CHANGELOG.md"
    if not path.is_file():
        print(f"post_release_changelog: missing {path}", file=sys.stderr)
        return 2

    original = path.read_text(encoding="utf-8")
    updated = insert_section(original, args.version, args.date)
    if updated is None:
        print(f"CHANGELOG.md already documents [{args.version}]; skipping.")
        return 0

    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"CHANGELOG.md: added section [{args.version}] - {args.date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
