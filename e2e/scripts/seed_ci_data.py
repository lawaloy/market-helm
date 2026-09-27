#!/usr/bin/env python3
"""Write representative E2E data using the app's trading-day rule (prevents auto-fetch)."""
from __future__ import annotations

import json
import os
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
    data_dir = Path(os.environ.get("DATA_DIR") or ROOT / "data").resolve()
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
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "close": 180.0,
                "change": 0.7,
                "change_percent": 0.4,
                "volume": 42_000_000,
                "index_name": "NASDAQ-100",
            },
            {
                "symbol": "TSLA",
                "name": "Tesla",
                "close": 420.0,
                "change": -5.9,
                "change_percent": -1.4,
                "volume": 31_000_000,
                "index_name": "NASDAQ-100",
            },
            {
                "symbol": "AMZN",
                "name": "Amazon",
                "close": 225.0,
                "change": -1.6,
                "change_percent": -0.7,
                "volume": 28_000_000,
                "index_name": "NASDAQ-100",
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
                "current_price": 150.0,
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
                "current_price": 350.0,
                "target_mid": 360.0,
                "recommendation": "BUY",
                "confidence": 78,
                "expected_change_percent": 2.9,
                "risk_level": "Low",
                "trend": "Bullish",
                "reason": "E2E fixture",
                "projection_date": day,
            },
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "current_price": 180.0,
                "target_mid": 181.5,
                "recommendation": "HOLD",
                "confidence": 65,
                "expected_change_percent": 0.8,
                "risk_level": "Medium",
                "trend": "Neutral",
                "reason": "E2E fixture",
                "projection_date": day,
            },
            {
                "symbol": "TSLA",
                "name": "Tesla",
                "current_price": 420.0,
                "target_mid": 409.5,
                "recommendation": "SELL",
                "confidence": 72,
                "expected_change_percent": -2.5,
                "risk_level": "High",
                "trend": "Bearish",
                "reason": "E2E fixture",
                "projection_date": day,
            },
            {
                "symbol": "AMZN",
                "name": "Amazon",
                "current_price": 225.0,
                "target_mid": 218.25,
                "recommendation": "STRONG SELL",
                "confidence": 80,
                "expected_change_percent": -3.0,
                "risk_level": "Medium",
                "trend": "Bearish",
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
                    "total_stocks": 5,
                    "gainers": 3,
                    "losers": 2,
                    "average_change_percent": -0.02,
                },
                "top_gainers": [
                    {"symbol": "AAPL", "change_percent": 1.0},
                    {"symbol": "MSFT", "change_percent": 0.6},
                    {"symbol": "NVDA", "change_percent": 0.4},
                ],
                "top_losers": [
                    {"symbol": "TSLA", "change_percent": -1.4},
                    {"symbol": "AMZN", "change_percent": -0.7},
                ],
            },
            "exchange_comparison": {
                "S&P 500": {"average_change_percent": 0.8, "gainers": 2, "losers": 0},
                "NASDAQ-100": {
                    "average_change_percent": -0.57,
                    "gainers": 1,
                    "losers": 2,
                },
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
