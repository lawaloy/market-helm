#!/usr/bin/env python3
"""
Single source of truth: setup.cfg [metadata] version.

  python scripts/version_sync.py check   # read-only: exit 1 if files disagree (CI)
  python scripts/version_sync.py sync    # write: copy setup.cfg → dashboard files

When this runs
--------------
* **Locally** — after you change ``setup.cfg`` ``version``, run ``sync`` and commit.
* **CI** (``.github/workflows/python-app.yml``) — ``check`` on every PR so drift fails the build.
* **Publish to PyPI** (``.github/workflows/publish.yml``) — ``check`` in the *test* job; ``sync`` in the
  *build* job **after** the release tag is applied to ``setup.cfg`` on the runner (so the SPA build
  matches the tag). Nothing is committed from CI; ``sync`` only fixes the checkout used for the wheel.

``check`` never modifies files. Only ``sync`` writes. Broken inputs (missing ``setup.cfg``, bad JSON,
missing markers in ``main.py``) print a short message to stderr and exit **2** (not a Python traceback).
"""
from __future__ import annotations

import argparse
import configparser
import json
import re
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _repo_rel_posix(root: Path, path: Path) -> str:
    """Path under root using forward slashes (stable check/CI output on Windows and POSIX)."""
    return path.relative_to(root).as_posix()


def read_setup_version(root: Path) -> str:
    cfg_path = root / "setup.cfg"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Missing {cfg_path}")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path, encoding="utf-8")
    if "metadata" not in cfg or "version" not in cfg["metadata"]:
        raise ValueError("setup.cfg missing [metadata] version")
    v = cfg["metadata"]["version"].strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise ValueError(f"Invalid semver in setup.cfg: {v!r}")
    return v


def read_package_json_version(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data.get("version", "")).strip()


def read_lock_root_versions(path: Path) -> tuple[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    top = str(data.get("version", "")).strip()
    inner = ""
    packages = data.get("packages") or {}
    if "" in packages and isinstance(packages[""], dict):
        inner = str(packages[""].get("version", "")).strip()
    return top, inner


def read_main_py_versions(path: Path) -> tuple[str | None, str | None]:
    """Return (fastapi_version, root_json_version) or (None, None) if markers are missing."""
    text = path.read_text(encoding="utf-8")
    fastapi = re.search(
        r'title="MarketHelm API",\s*\n\s*description="[^"]+",\s*\n\s*version="(\d+\.\d+\.\d+)"',
        text,
    )
    root_json = re.search(
        r'"service": "MarketHelm API",\s*\n\s*"version": "(\d+\.\d+\.\d+)"',
        text,
    )
    if not fastapi or not root_json:
        return None, None
    return fastapi.group(1), root_json.group(1)


def check(root: Path) -> list[str]:
    want = read_setup_version(root)
    errors: list[str] = []

    pj = root / "dashboard" / "frontend" / "package.json"
    got = read_package_json_version(pj)
    if got != want:
        errors.append(f"{_repo_rel_posix(root, pj)}: version is {got!r}, setup.cfg has {want!r}")

    lock = root / "dashboard" / "frontend" / "package-lock.json"
    top, inner = read_lock_root_versions(lock)
    if top != want:
        errors.append(f"{_repo_rel_posix(root, lock)} root version: {top!r} != {want!r}")
    if inner != want:
        errors.append(
            f'{_repo_rel_posix(root, lock)} packages[""] version: {inner!r} != {want!r}'
        )

    main_py = root / "dashboard" / "backend" / "main.py"
    fa, rj = read_main_py_versions(main_py)
    if fa is None or rj is None:
        errors.append(
            f"{_repo_rel_posix(root, main_py)}: could not read version markers "
            '(expected FastAPI "MarketHelm API" block and root() JSON). Run sync after fixing the file.'
        )
    else:
        if fa != want:
            errors.append(f"{_repo_rel_posix(root, main_py)} FastAPI version: {fa!r} != {want!r}")
        if rj != want:
            errors.append(f"{_repo_rel_posix(root, main_py)} root JSON version: {rj!r} != {want!r}")

    return errors


def sync_package_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def sync_package_lock(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    if "packages" in data and "" in data["packages"] and isinstance(data["packages"][""], dict):
        data["packages"][""]["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def sync_main_py(path: Path, version: str) -> str | None:
    """
    Update version strings in main.py. Returns None on success, or an error message.
    """
    text = path.read_text(encoding="utf-8")
    new_text, n1 = re.subn(
        r'(title="MarketHelm API",\s*\n\s*description="[^"]+",\s*\n\s*version=")(\d+\.\d+\.\d+)(")',
        rf"\g<1>{version}\3",
        text,
        count=1,
    )
    if n1 != 1:
        return (
            f"Could not find the FastAPI 'MarketHelm API' version= line in {path} "
            f"(expected exactly one match, got {n1}). Edit the file manually, then run sync again."
        )
    new_text, n2 = re.subn(
        r'("service": "MarketHelm API",\s*\n\s*"version": ")(\d+\.\d+\.\d+)(")',
        rf"\g<1>{version}\3",
        new_text,
        count=1,
    )
    if n2 != 1:
        return (
            f"Could not find the root JSON version next to 'MarketHelm API' in {path} "
            f"(expected exactly one match, got {n2}). Edit the file manually, then run sync again."
        )
    path.write_text(new_text, encoding="utf-8", newline="\n")
    return None


def cmd_check(root: Path) -> int:
    errors = check(root)
    if errors:
        print("Version mismatch (canonical: setup.cfg [metadata] version):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\nTo fix locally: python scripts/version_sync.py sync", file=sys.stderr)
        return 1
    print(f"OK: all tracked files match setup.cfg version {read_setup_version(root)!r}")
    return 0


def cmd_sync(root: Path) -> int:
    version = read_setup_version(root)
    sync_package_json(root / "dashboard" / "frontend" / "package.json", version)
    sync_package_lock(root / "dashboard" / "frontend" / "package-lock.json", version)
    err = sync_main_py(root / "dashboard" / "backend" / "main.py", version)
    if err:
        print(f"sync: {err}", file=sys.stderr)
        return 2
    print(f"Synced dashboard files to {version!r} from setup.cfg")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="Read-only: fail if dashboard files disagree with setup.cfg")
    sub.add_parser("sync", help="Write: copy setup.cfg version into dashboard files")
    args = parser.parse_args()
    root = repo_root()
    try:
        if args.cmd == "check":
            return cmd_check(root)
        if args.cmd == "sync":
            return cmd_sync(root)
    except FileNotFoundError as e:
        print(f"version_sync: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"version_sync: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"version_sync: invalid JSON ({e})", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
