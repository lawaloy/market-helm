#!/usr/bin/env python3
"""
Check (or fix) Python style on the files a branch changed.

CI runs this on pull requests so new and touched code follows the style that
CONTRIBUTING.md documents without mass-reformatting the whole repository:

* black and isort (``--profile black``, line length 100, configured in
  ``pyproject.toml``) are blocking.
* flake8 at 100 characters (configured in ``.flake8``) is blocking too. Only the
  files a PR changes are checked, so legacy findings elsewhere do not fail it.
  Pass ``--report-only-flake8`` to print flake8 findings without failing.

Usage:
    python scripts/check_python_style.py --base origin/main
    python scripts/check_python_style.py --base origin/main --fix
    python scripts/check_python_style.py --all
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PARTS = {".venv", ".venv-audit", "build", "dist", "node_modules", "markethelm.egg-info"}


def filter_python_files(paths: Sequence[str]) -> List[str]:
    """Keep existing ``.py`` files outside vendored/build directories."""
    kept: List[str] = []
    for raw in paths:
        path = raw.strip().replace("\\", "/")
        if not path.endswith(".py"):
            continue
        if EXCLUDED_PARTS.intersection(path.split("/")):
            continue
        if not (REPO_ROOT / path).is_file():
            continue
        kept.append(path)
    return sorted(set(kept))


def _git_lines(args: Sequence[str]) -> List[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.splitlines()


def changed_python_files(base: str) -> List[str]:
    """Python files added/changed/renamed since the merge base with ``base``."""
    try:
        lines = _git_lines(["diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"])
    except RuntimeError:
        lines = _git_lines(["diff", "--name-only", "--diff-filter=ACMR", base])
    return filter_python_files(lines)


def all_python_files() -> List[str]:
    return filter_python_files(_git_lines(["ls-files", "*.py"]))


def tool_command(module: str, *args: str) -> List[str]:
    return [sys.executable, "-m", module, *args]


E203_HINT = (
    "hint: E203 means black wrote a space before ':' in a slice with complex bounds, e.g.\n"
    "  ham[lower + offset : upper + offset]\n"
    "flake8 rejects that spacing and black will not change it, so assign the bounds to\n"
    "named variables instead (see CONTRIBUTING.md, 'Check Code Quality'):\n"
    "  start = lower + offset\n"
    "  stop = upper + offset\n"
    "  ham[start:stop]"
)


def run_tool(label: str, command: Sequence[str]) -> int:
    print(f"==> {label}")
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    if " E203 " in output:
        print(E203_HINT)
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--base", default="origin/main", help="Git ref to diff against (default: origin/main)"
    )
    scope.add_argument("--all", action="store_true", help="Check every tracked Python file")
    parser.add_argument(
        "--fix", action="store_true", help="Apply black and isort instead of checking"
    )
    parser.add_argument(
        "--report-only-flake8",
        action="store_true",
        help="Print flake8 findings without failing the run",
    )
    args = parser.parse_args(argv)

    files = all_python_files() if args.all else changed_python_files(args.base)
    if not files:
        print("No Python files to check.")
        return 0
    print(f"Checking {len(files)} Python file(s).")

    failures = 0
    if args.fix:
        run_tool("isort", tool_command("isort", *files))
        run_tool("black", tool_command("black", *files))
        return 0

    if run_tool("black --check", tool_command("black", "--check", "--diff", "--quiet", *files)):
        failures += 1
        print(
            "black would reformat the files above; run: python scripts/check_python_style.py --fix"
        )
    if run_tool("isort --check-only", tool_command("isort", "--check-only", "--diff", *files)):
        failures += 1
        print("isort would reorder imports; run: python scripts/check_python_style.py --fix")
    flake8_status = run_tool("flake8 (max-line-length 100)", tool_command("flake8", *files))
    if flake8_status:
        if args.report_only_flake8:
            print("flake8 findings are informational (--report-only-flake8).")
        else:
            failures += 1
            print("flake8 found problems in the changed files above; fix them before merging.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
