"""Deterministic projection backtesting over saved MarketHelm snapshots."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import math
from pathlib import Path
import re
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd

from .market_calendar import (
    DEFAULT_CALENDAR,
    get_market_calendar,
    trading_session_after,
)
from ..utils.tickers import normalize_ticker

_DATED_FILE = re.compile(r"^(daily_data|projections)_(\d{4}-\d{2}-\d{2})\.csv$")
_INVALID_LABELS = frozenset({"", "nan", "<na>", "none", "nat", "null"})


def _finite_positive(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _finite_confidence(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 100 else None


def _label(value: Any, default: str = "UNKNOWN") -> str:
    try:
        text = str(value).strip()
    except Exception:
        return default
    return default if text.lower() in _INVALID_LABELS else text


def _direction(value: float, origin: float) -> int:
    return 1 if value > origin else -1 if value < origin else 0


def _mean(values: Iterable[float]) -> Optional[float]:
    items = list(values)
    return sum(items) / len(items) if items else None


def _rounded(value: Optional[float], places: int = 3) -> Optional[float]:
    return round(value, places) if value is not None else None


def _confidence_band(confidence: Optional[float]) -> str:
    if confidence is None:
        return "UNKNOWN"
    lower = min(int(confidence // 10) * 10, 90)
    if lower < 50:
        return "0-49"
    return f"{lower}-{lower + 9 if lower < 90 else 100}"


def _aggregate(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors = [sample["absErrorPct"] for sample in samples]
    directions = [sample for sample in samples if sample["directionCorrect"] is not None]
    bands = [sample for sample in samples if sample["bandHit"] is not None]
    calibrated = [sample for sample in directions if sample["confidence"] is not None]
    direction_accuracy = _mean(float(sample["directionCorrect"]) * 100 for sample in directions)
    mean_confidence = _mean(sample["confidence"] for sample in calibrated)
    calibrated_accuracy = _mean(
        float(sample["directionCorrect"]) * 100 for sample in calibrated
    )
    return {
        "count": len(samples),
        "meanAbsErrorPct": _rounded(_mean(errors)),
        "medianAbsErrorPct": _rounded(median(errors) if errors else None),
        "directionalAccuracyPct": _rounded(direction_accuracy),
        "bandCoveragePct": _rounded(
            _mean(float(sample["bandHit"]) * 100 for sample in bands)
        ),
        "meanConfidence": _rounded(mean_confidence),
        "calibrationGapPct": _rounded(
            mean_confidence - calibrated_accuracy
            if mean_confidence is not None and calibrated_accuracy is not None
            else None
        ),
    }


def evaluate_projections(
    projections: Iterable[Mapping[str, Any]],
    closes: Iterable[Mapping[str, Any]],
    *,
    horizon_sessions: int = 5,
    calendar_name: str = DEFAULT_CALENDAR,
    max_samples: Optional[int] = 300,
) -> Dict[str, Any]:
    """Evaluate projection rows against the exact target exchange session.

    Each projection must include ``run_date``, ``symbol``, and ``target_mid``.
    Actual rows must include ``date``, ``symbol``, and ``close``. Missing closes
    on the target session are reported as missing rather than rolled forward,
    keeping every sample on the same horizon and preventing accidental look-ahead.
    """
    if horizon_sessions < 1:
        raise ValueError("horizon_sessions must be at least 1")
    get_market_calendar(calendar_name)

    projection_rows = list(projections)
    close_map: Dict[Tuple[str, str], float] = {}
    observed_dates = set()
    for row in closes:
        symbol = normalize_ticker(row.get("symbol"))
        close = _finite_positive(row.get("close"))
        try:
            actual_date = datetime.strptime(str(row.get("date"))[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if symbol and close is not None:
            close_map[(actual_date.isoformat(), symbol)] = close
            observed_dates.add(actual_date)

    latest_observed = max(observed_dates) if observed_dates else None
    samples: List[Dict[str, Any]] = []
    invalid_count = 0
    pending_count = 0
    missing_actual_count = 0

    for row in projection_rows:
        symbol = normalize_ticker(row.get("symbol"))
        predicted = _finite_positive(row.get("target_mid"))
        try:
            run_date = datetime.strptime(str(row.get("run_date"))[:10], "%Y-%m-%d").date()
            target_date = trading_session_after(run_date, horizon_sessions, calendar_name)
        except (TypeError, ValueError):
            invalid_count += 1
            continue
        if not symbol or predicted is None:
            invalid_count += 1
            continue
        if latest_observed is None or target_date > latest_observed:
            pending_count += 1
            continue

        actual = close_map.get((target_date.isoformat(), symbol))
        if actual is None:
            missing_actual_count += 1
            continue

        current = _finite_positive(row.get("current_price"))
        target_low = _finite_positive(row.get("target_low"))
        target_high = _finite_positive(row.get("target_high"))
        confidence = _finite_confidence(row.get("confidence"))
        direction_correct = None
        if current is not None:
            direction_correct = _direction(predicted, current) == _direction(actual, current)
        band_hit = None
        if target_low is not None and target_high is not None and target_low <= target_high:
            band_hit = target_low <= actual <= target_high

        samples.append(
            {
                "symbol": symbol,
                "runDate": run_date.isoformat(),
                "targetDate": target_date.isoformat(),
                "actualDate": target_date.isoformat(),
                "current": _rounded(current, 4),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "absErrorPct": round(abs(predicted - actual) / actual * 100, 3),
                "signedErrorPct": round((predicted - actual) / actual * 100, 3),
                "directionCorrect": direction_correct,
                "bandHit": band_hit,
                "confidence": _rounded(confidence, 2),
                "confidenceBand": _confidence_band(confidence),
                "recommendation": _label(row.get("recommendation")),
            }
        )

    by_recommendation: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_confidence: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_recommendation[sample["recommendation"]].append(sample)
        by_confidence[sample["confidenceBand"]].append(sample)

    mature_count = len(samples) + missing_actual_count
    summary = {
        "schemaVersion": 1,
        "calendar": calendar_name,
        "horizonSessions": horizon_sessions,
        "projectionCount": len(projection_rows),
        "validProjectionCount": len(projection_rows) - invalid_count,
        "sampleCount": len(samples),
        "invalidCount": invalid_count,
        "pendingCount": pending_count,
        "missingActualCount": missing_actual_count,
        "evaluationCoveragePct": _rounded(
            len(samples) / mature_count * 100 if mature_count else None
        ),
        **{key: value for key, value in _aggregate(samples).items() if key != "count"},
        "byRecommendation": {
            key: _aggregate(value) for key, value in sorted(by_recommendation.items())
        },
        "byConfidenceBand": {
            key: _aggregate(value) for key, value in sorted(by_confidence.items())
        },
    }
    visible_samples = samples if max_samples is None else samples[:max_samples]
    return {
        "summary": summary,
        "samples": visible_samples,
        "samplesTruncated": len(visible_samples) < len(samples),
    }


def backtest_data_dir(
    data_dir: Path,
    *,
    days: int = 365,
    horizon_sessions: int = 5,
    calendar_name: str = DEFAULT_CALENDAR,
    max_samples: Optional[int] = 300,
) -> Dict[str, Any]:
    """Load dated snapshot CSVs from ``data_dir`` and evaluate projections."""
    root = Path(data_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Data directory not found: {root}")
    if days < 1:
        raise ValueError("days must be at least 1")

    dated_files: List[Tuple[str, str, Path]] = []
    for path in root.glob("*.csv"):
        match = _DATED_FILE.fullmatch(path.name)
        if match:
            try:
                datetime.strptime(match.group(2), "%Y-%m-%d")
            except ValueError:
                continue
            dated_files.append((match.group(1), match.group(2), path))
    dated_files.sort(key=lambda item: (item[1], item[0], item[2].name))
    daily_files = [(day, path) for kind, day, path in dated_files if kind == "daily_data"]
    if not daily_files:
        return evaluate_projections(
            [],
            [],
            horizon_sessions=horizon_sessions,
            calendar_name=calendar_name,
            max_samples=max_samples,
        )

    latest = max(datetime.strptime(day, "%Y-%m-%d").date() for day, _ in daily_files)
    cutoff = latest - timedelta(days=days)
    projections: List[Dict[str, Any]] = []
    closes: List[Dict[str, Any]] = []

    for day, path in daily_files:
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        for row in frame.to_dict("records"):
            closes.append({**row, "date": day})

    for kind, day, path in dated_files:
        if kind != "projections" or datetime.strptime(day, "%Y-%m-%d").date() < cutoff:
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        for row in frame.to_dict("records"):
            projections.append({**row, "run_date": day})

    return evaluate_projections(
        projections,
        closes,
        horizon_sessions=horizon_sessions,
        calendar_name=calendar_name,
        max_samples=max_samples,
    )
