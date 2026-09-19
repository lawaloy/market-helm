#!/usr/bin/env python3
"""Write minimal dashboard data for E2E/CI using the same trading-day rule as the app (prevents auto-fetch)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo root (e2e/scripts -> parents[2])
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.backend.services.data_loader import get_most_recent_trading_day  # noqa: E402
from src.storage.market_bars import upsert_market_bars  # noqa: E402
from src.storage.projections_store import upsert_daily_summary, upsert_projections  # noqa: E402


def main() -> None:
    day = get_most_recent_trading_day()
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    upsert_market_bars(
        [
            {
                "symbol": "AAPL",
                "name": "Apple",
                "close": 150.0,
                "change": 1.5,
                "change_percent": 1.0,
                "volume": 50_000_000,
                "index_name": "S&P 500",
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft",
                "close": 350.0,
                "change": 2.1,
                "change_percent": 0.6,
                "volume": 25_000_000,
                "index_name": "S&P 500",
            },
        ],
        day,
        data_dir=data_dir,
        source="e2e",
    )

    upsert_projections(
        [
            {
                "symbol": "AAPL",
                "name": "Apple",
                "target_mid": 155.0,
                "recommendation": "STRONG BUY",
                "confidence": 85,
                "expected_change_percent": 3.3,
                "risk_level": "Medium",
                "trend": "Bullish",
                "reason": "E2E fixture",
                "projection_date": day,
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft",
                "target_mid": 360.0,
                "recommendation": "HOLD",
                "confidence": 55,
                "expected_change_percent": 2.9,
                "risk_level": "Low",
                "trend": "Bullish",
                "reason": "E2E fixture",
                "projection_date": day,
            },
        ],
        day,
        data_dir=data_dir,
        source="e2e",
    )

    upsert_daily_summary(
        {
            "date": day,
            "analysis": {
                "date": day,
                "summary": {
                    "total_stocks": 2,
                    "gainers": 2,
                    "losers": 0,
                    "average_change_percent": 0.8,
                },
                "top_gainers": [
                    {"symbol": "AAPL", "change_percent": 1.0},
                    {"symbol": "MSFT", "change_percent": 0.6},
                ],
                "top_losers": [],
            },
            "exchange_comparison": {
                "S&P 500": {"average_change_percent": 0.8, "gainers": 2, "losers": 0},
            },
        },
        day,
        data_dir=data_dir,
        source="e2e",
    )

    history = {
        "last_triggered": {},
        "events": [],
        "delivery_log": [
            {
                "alert_id": "e2e_watch",
                "channel": "email",
                "success": True,
                "test": True,
                "timestamp": "2026-06-21T12:00:00",
            },
            {
                "alert_id": "e2e_watch",
                "channel": "webhook",
                "success": False,
                "test": False,
                "timestamp": "2026-06-20T08:30:00",
            },
        ],
    }
    with open(data_dir / "alerts_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f)

    print(f"Seeded data for trading day {day} under {data_dir}")


if __name__ == "__main__":
    main()
