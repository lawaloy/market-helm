#!/usr/bin/env python3
"""
Script to check markdown files for linting errors.

Usage:
    python scripts/check_markdown.py                 # Check all markdown files
    python scripts/check_markdown.py path/to/file.md # Check specific file
    python scripts/check_markdown.py --fix           # Auto-fix issues
"""

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from read_lints import read_lints
except ImportError:
    read_lints = None


def find_markdown_files(directory="."):
    """Find all markdown files in the project."""
    project_root = Path(directory)

    # Directories to exclude
    exclude_dirs = {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".git",
        ".pytest_cache",
        "dist",
        "build",
        "*.egg-info",
    }

    md_files = []
    for md_file in project_root.rglob("*.md"):
        # Skip excluded directories
        if any(excluded in str(md_file) for excluded in exclude_dirs):
            continue
        md_files.append(md_file)

    return sorted(md_files)


def check_markdown_with_markdownlint(files, fix=False):
    """Check markdown files using markdownlint-cli if available."""
    try:
        cmd = ["markdownlint"]

        if fix:
            cmd.append("--fix")

        cmd.extend([str(f) for f in files])

        # On Windows, use shell=True to find .cmd files
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
        )

        if result.returncode == 0:
            print(f"All {len(files)} markdown files are clean!")
            return True
        else:
            print(f"Found markdown linting errors:\n")
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return False

    except FileNotFoundError:
        print("markdownlint-cli not found. Install with:")
        print("   npm install -g markdownlint-cli")
        print("\nFalling back to Python linter check...")
        return check_markdown_with_python(files)


def check_markdown_with_python(files):
    """Check markdown files using Python's built-in linter."""
    if read_lints is None:
        print("Python linter not available")
        print("Please install markdownlint-cli:")
        print("   npm install -g markdownlint-cli")
        return False

    try:
        errors_found = False
        for md_file in files:
            result = read_lints([str(md_file)])
            if result:
                errors_found = True
                print(f"\n{md_file}:")
                print(result)

        if not errors_found:
            print(f"All {len(files)} markdown files are clean!")
            return True
        return False

    except Exception as e:
        print(f"Error checking markdown: {e}")
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Check markdown files for linting errors")
    parser.add_argument("files", nargs="*", help="Specific markdown files to check (default: all)")
    parser.add_argument("--fix", action="store_true", help="Automatically fix fixable issues")
    parser.add_argument("--dir", default=".", help="Directory to search for markdown files")

    args = parser.parse_args()

    # Get files to check
    if args.files:
        md_files = [Path(f) for f in args.files]
    else:
        print(f"Searching for markdown files in {args.dir}...")
        md_files = find_markdown_files(args.dir)
        print(f"Found {len(md_files)} markdown files\n")

    if not md_files:
        print("No markdown files found.")
        return 0

    # Check the files
    success = check_markdown_with_markdownlint(md_files, fix=args.fix)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
