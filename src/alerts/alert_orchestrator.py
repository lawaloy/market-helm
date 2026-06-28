"""Enqueue symbol-centric evaluation jobs from a shared market snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.alerts.market_snapshot import load_market_snapshot
from src.storage.alert_jobs import JOB_EVALUATE_SYMBOL, enqueue_jobs
from src.storage.alert_watches import list_enabled_symbols
from src.storage.database import database_enabled, init_database


def run_orchestrator_tick() -> Dict[str, Any]:
    """Load market data once and enqueue one evaluate_symbol job per watched symbol."""
    if not database_enabled():
        raise RuntimeError("Orchestrator requires MARKET_HELM_DATABASE_URL")

    init_database()
    symbols = list_enabled_symbols()
    if not symbols:
        return {
            "tick_id": None,
            "enqueued": 0,
            "last_data_date": None,
            "message": "No enabled watches in database.",
        }

    last_date, prices, _stocks = load_market_snapshot(symbols, fetch_missing_quotes=True)
    if not prices:
        return {
            "tick_id": None,
            "enqueued": 0,
            "last_data_date": last_date,
            "message": "No market data available.",
        }

    tick_id = datetime.now(timezone.utc).isoformat()
    dedupe_key = tick_id
    payloads: List[Dict[str, Any]] = []

    for symbol in symbols:
        price = prices.get(symbol)
        if price is None:
            continue
        payloads.append(
            {
                "tick_id": tick_id,
                "dedupe_key": dedupe_key,
                "symbol": symbol,
                "price": price,
                "last_data_date": last_date,
            }
        )

    enqueued = enqueue_jobs(JOB_EVALUATE_SYMBOL, payloads)
    return {
        "tick_id": tick_id,
        "enqueued": enqueued,
        "last_data_date": last_date,
        "message": None if enqueued else "No priced symbols for enabled watches.",
    }
