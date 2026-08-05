"""
Market API endpoints
"""
import math
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from dashboard.backend.models.market import MarketOverview, MoversResponse, StockMover, IndexData
from dashboard.backend.services.data_loader import get_data_loader

router = APIRouter()


def _numeric_change_percent(df: pd.DataFrame) -> pd.Series:
    """Coerce change_percent so dirty CSV cells cannot TypeError overview/movers."""
    change = pd.to_numeric(df["change_percent"], errors="coerce")
    return change.where(change.map(lambda value: pd.notna(value) and math.isfinite(float(value))))


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce numeric summary fields; fall back when missing, non-numeric, or non-finite."""
    try:
        if value is None:
            return default
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _overview_index_key(index_name: Any) -> Optional[str]:
    """Build overview indices key; skip blank/NaN names that cannot .replace."""
    if index_name is None:
        return None
    if isinstance(index_name, float) and not math.isfinite(index_name):
        return None
    try:
        text = str(index_name).strip()
    except Exception:
        return None
    if not text or text.lower() in {"nan", "<na>", "none"}:
        return None
    return text.replace(" ", "")


def _as_dict(value: Any) -> Dict[str, Any]:
    """Return value when it is a dict; otherwise {} for corrupt summary nests."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    """Return value when it is a list; otherwise [] for corrupt mover arrays."""
    return value if isinstance(value, list) else []


def _finite_float(value: Any) -> Optional[float]:
    """Return float when finite; otherwise None (missing/non-numeric/NaN/Inf)."""
    try:
        if value is None:
            return None
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _safe_label(value: Any, default: str) -> str:
    """Return a display label; blank/NaN sentinels fall back instead of crashing."""
    if value is None:
        return default
    try:
        text = str(value).strip()
    except Exception:
        return default
    if not text or text.lower() in {"nan", "<na>", "none"}:
        return default
    return text


def _safe_volume(value: Any) -> int:
    """Coerce volume to a finite int; bad/missing cells become 0 (never abort the list)."""
    try:
        if value is None:
            return 0
        result = float(value)
        if not math.isfinite(result):
            return 0
        return int(result)
    except (TypeError, ValueError):
        return 0


def _generate_demo_summary(analysis: Dict[str, Any], exchange_comparison: Dict[str, Any]) -> str:
    """Generate a template-based summary when ai_summary is not in the JSON."""
    # Corrupt summary JSON can nest strings/lists where objects/arrays are
    # expected; soft-fail so /api/summary stays 200 with a usable demo template.
    analysis = _as_dict(analysis)
    exchange_comparison = _as_dict(exchange_comparison)
    summary_data = _as_dict(analysis.get("summary"))
    top_gainers = _as_list(analysis.get("top_gainers"))[:2]
    top_losers = _as_list(analysis.get("top_losers"))[:2]

    summary_parts = []
    gainers = int(_safe_float(summary_data.get("gainers", 0)))
    losers = int(_safe_float(summary_data.get("losers", 0)))
    avg_change = _safe_float(summary_data.get("average_change_percent", 0))

    if gainers > losers:
        sentiment = "positive"
    elif losers > gainers:
        sentiment = "negative"
    else:
        sentiment = "mixed"

    summary_parts.append(
        f"Today's market showed {sentiment} sentiment with {gainers} gainers and {losers} losers, "
        f"averaging {avg_change:.2f}% change overall."
    )

    if top_gainers:
        top_gainer = _as_dict(top_gainers[0])
        symbol = top_gainer.get("symbol")
        if symbol is not None and "change_percent" in top_gainer:
            change = _safe_float(top_gainer.get("change_percent"))
            summary_parts.append(
                f"{symbol} led gains with a {change:.2f}% increase."
            )

    if top_losers:
        top_loser = _as_dict(top_losers[0])
        symbol = top_loser.get("symbol")
        if symbol is not None and "change_percent" in top_loser:
            change = _safe_float(top_loser.get("change_percent"))
            summary_parts.append(
                f"{symbol} declined {abs(change):.2f}%, "
                "marking the largest drop."
            )

    items = [
        (name, stats if isinstance(stats, dict) else {})
        for name, stats in exchange_comparison.items()
    ]
    if items:
        best = max(
            items,
            key=lambda x: _safe_float(x[1].get("average_change_percent", 0)),
        )
        exchange_name, stats = best
        avg_exchange = _safe_float(stats.get("average_change_percent", 0))
        summary_parts.append(
            f"The {exchange_name} exchange performed best with an average "
            f"{avg_exchange:.2f}% gain."
        )

    return " ".join(summary_parts)


@router.get("/overview", response_model=MarketOverview)
async def get_market_overview():
    """Get market overview with statistics"""
    try:
        loader = get_data_loader()
        date = loader.get_latest_date()
        
        if not date:
            raise HTTPException(status_code=404, detail="No data available")
        
        # Load daily data
        df = loader.load_daily_data()
        if df is None or getattr(df, "empty", False) or "change_percent" not in df.columns:
            raise HTTPException(status_code=404, detail="No data available.")

        # Dirty cells ("bad"/mixed types) promote object dtype and TypeError
        # comparisons / mean / nlargest — coerce once for all overview stats.
        change = _numeric_change_percent(df)

        # Calculate overall statistics
        total_stocks = len(df)
        gainers = int((change > 0).sum())
        losers = int((change < 0).sum())
        unchanged = int((change == 0).sum())

        avg_change = _safe_float(change.mean())
        max_change = _safe_float(change.max())
        min_change = _safe_float(change.min())

        # Calculate per-index statistics
        indices = {}
        if 'index_name' in df.columns:
            for index_name in df['index_name'].unique():
                key = _overview_index_key(index_name)
                if key is None:
                    # Corrupt/missing index labels previously AttributeError'd on
                    # .replace and 500'd the whole overview payload.
                    continue
                index_mask = df['index_name'] == index_name
                index_change = change[index_mask]
                indices[key] = IndexData(
                    stocks=int(index_mask.sum()),
                    avgChange=round(_safe_float(index_change.mean()), 2),
                    gainers=int((index_change > 0).sum()),
                    losers=int((index_change < 0).sum()),
                )
        
        return MarketOverview(
            date=date,
            totalStocks=total_stocks,
            gainers=gainers,
            losers=losers,
            unchanged=unchanged,
            averageChange=round(avg_change, 2),
            maxChange=round(max_change, 2),
            minChange=round(min_change, 2),
            indices=indices
        )
    
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/movers", response_model=MoversResponse)
async def get_top_movers(
    type: str = Query("gainers", pattern="^(gainers|losers)$"),
    limit: int = Query(10, ge=1, le=50)
):
    """Get top gainers or losers"""
    try:
        loader = get_data_loader()
        df = loader.load_daily_data()
        if df is None or getattr(df, "empty", False) or "change_percent" not in df.columns:
            raise HTTPException(status_code=404, detail="No data available.")

        # Coerce before nlargest — object-dtype change_percent TypeErrors ranking.
        ranked = df.copy()
        ranked["_change_percent"] = _numeric_change_percent(ranked)
        ranked = ranked[ranked["_change_percent"].notna()]

        # Filter by sign first so a large limit cannot mix gainers into losers
        # (or vice versa) when fewer matching movers exist than `limit`.
        if type == "gainers":
            sorted_df = ranked[ranked["_change_percent"] > 0].nlargest(
                limit, "_change_percent"
            )
        else:
            sorted_df = ranked[ranked["_change_percent"] < 0].nsmallest(
                limit, "_change_percent"
            )

        movers = []
        for _, row in sorted_df.iterrows():
            # Skip non-finite price fields so one corrupt CSV row cannot null the payload
            # or abort the whole movers card via int(float('nan')).
            price = _finite_float(row.get('close'))
            change = _finite_float(row.get('change'))
            change_percent = _finite_float(row.get('_change_percent'))
            if price is None or change is None or change_percent is None:
                continue
            symbol = row.get("symbol")
            if symbol is None or (isinstance(symbol, float) and not math.isfinite(symbol)):
                continue
            symbol_text = str(symbol).strip()
            if not symbol_text:
                continue
            movers.append(StockMover(
                symbol=symbol_text,
                # Dirty CSV name cells (NaN/None) fail Pydantic str → 500 the card.
                name=_safe_label(row.get('name'), symbol_text),
                price=price,
                change=change,
                changePercent=change_percent,
                volume=_safe_volume(row.get('volume', 0)),
            ))
        
        return MoversResponse(type=type, data=movers)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


async def get_market_summary():
    """Get market summary (AI-generated if available, otherwise demo summary)."""
    try:
        loader = get_data_loader()
        summary_data = loader.load_summary()
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    ai_summary = summary_data.get("ai_summary")
    date_str: str = summary_data.get("date", "")

    # Non-string truthy ai_summary (e.g. number) must not AttributeError on .strip().
    if isinstance(ai_summary, str) and ai_summary.strip():
        return {
            "date": date_str,
            "summary": ai_summary.strip(),
            "source": "ai",
        }

    analysis = summary_data.get("analysis", {})
    exchange_comparison = summary_data.get("exchange_comparison", {})
    demo_summary = _generate_demo_summary(analysis, exchange_comparison)

    return {
        "date": date_str,
        "summary": demo_summary,
        "source": "demo",
    }
