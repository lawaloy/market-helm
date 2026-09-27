"""One-time migration of legacy market-data files into durable storage."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from .database import database_enabled
from .market_bars import (
    default_sidecar_path,
    list_market_bar_dates,
    upsert_market_bars,
)
from .projections_store import (
    list_projection_dates,
    list_summary_dates,
    upsert_daily_summary,
    upsert_projections,
)

_LEGACY_FILE = re.compile(
    r"^(daily_data|projections|summary)_(\d{4}-\d{2}-\d{2})\.(csv|json)$"
)
_DATE_LIMIT = 100_000


def _strict_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _legacy_files(data_dir: Path) -> Dict[str, List[tuple[str, Path]]]:
    found: Dict[str, List[tuple[str, Path]]] = {
        "daily_data": [],
        "projections": [],
        "summary": [],
    }
    for path in data_dir.iterdir():
        if not path.is_file():
            continue
        match = _LEGACY_FILE.fullmatch(path.name)
        if match is None:
            continue
        kind, raw_day, extension = match.groups()
        expected = "json" if kind == "summary" else "csv"
        if extension != expected:
            continue
        try:
            day = date.fromisoformat(raw_day).isoformat()
        except ValueError:
            continue
        found[kind].append((day, path))
    for files in found.values():
        files.sort(key=lambda item: (item[0], item[1].name))
    return found


def _csv_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        return [dict(row) for row in reader]


def _summary(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle, parse_constant=_strict_json_constant)
    if not isinstance(payload, dict):
        raise ValueError("summary JSON must contain an object")
    return payload


def _stats(discovered: int) -> Dict[str, int]:
    return {
        "discovered_files": discovered,
        "imported_files": 0,
        "skipped_existing_files": 0,
        "rows_written": 0,
        "invalid_rows": 0,
    }


def backfill_legacy_market_data(
    data_dir: str | Path,
    *,
    replace_existing: bool = False,
) -> Dict[str, Any]:
    """
    Import dated legacy CSV/JSON snapshots into durable market-data tables.

    Existing dates are skipped by default so an old file cannot overwrite a
    newer durable snapshot. The source files are never changed or deleted.
    Good files continue importing when a sibling file is malformed; callers can
    use the returned ``errors`` list to fail an operational run.
    """
    root = Path(data_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Data directory not found: {root}")

    files = _legacy_files(root)
    report: Dict[str, Any] = {
        "data_dir": str(root),
        "target": (
            "configured_database"
            if database_enabled()
            else str(default_sidecar_path(root))
        ),
        "replace_existing": bool(replace_existing),
        "daily_data": _stats(len(files["daily_data"])),
        "projections": _stats(len(files["projections"])),
        "summaries": _stats(len(files["summary"])),
        "errors": [],
    }

    if not any(files.values()):
        return report

    existing_bars = set(list_market_bar_dates(data_dir=root, limit=_DATE_LIMIT))
    existing_projections = set(
        list_projection_dates(data_dir=root, limit=_DATE_LIMIT)
    )
    existing_summaries = set(list_summary_dates(data_dir=root, limit=_DATE_LIMIT))

    for day, path in files["daily_data"]:
        stats = report["daily_data"]
        if day in existing_bars and not replace_existing:
            stats["skipped_existing_files"] += 1
            continue
        try:
            rows = _csv_rows(path)
            written = upsert_market_bars(
                rows, day, data_dir=root, source="legacy_csv"
            )
            if written <= 0:
                raise ValueError("file contains no valid market-bar rows")
            stats["imported_files"] += 1
            stats["rows_written"] += written
            stats["invalid_rows"] += max(0, len(rows) - written)
            existing_bars.add(day)
        except Exception as exc:
            report["errors"].append({"file": path.name, "error": str(exc)})

    for day, path in files["projections"]:
        stats = report["projections"]
        if day in existing_projections and not replace_existing:
            stats["skipped_existing_files"] += 1
            continue
        try:
            rows = _csv_rows(path)
            written = upsert_projections(
                rows, day, data_dir=root, source="legacy_csv"
            )
            if written <= 0:
                raise ValueError("file contains no valid projection rows")
            stats["imported_files"] += 1
            stats["rows_written"] += written
            stats["invalid_rows"] += max(0, len(rows) - written)
            existing_projections.add(day)
        except Exception as exc:
            report["errors"].append({"file": path.name, "error": str(exc)})

    for day, path in files["summary"]:
        stats = report["summaries"]
        if day in existing_summaries and not replace_existing:
            stats["skipped_existing_files"] += 1
            continue
        try:
            upsert_daily_summary(
                _summary(path), day, data_dir=root, source="legacy_json"
            )
            stats["imported_files"] += 1
            stats["rows_written"] += 1
            existing_summaries.add(day)
        except Exception as exc:
            report["errors"].append({"file": path.name, "error": str(exc)})

    return report
