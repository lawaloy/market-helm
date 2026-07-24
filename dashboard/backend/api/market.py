"""
Market API endpoints
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from dashboard.backend.models.market import MarketOverview, MoversResponse, StockMover, IndexData
from dashboard.backend.services.data_loader import get_data_loader

router = APIRouter()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce numeric summary fields; fall back when missing or non-numeric."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _generate_demo_summary(analysis: Dict[str, Any], exchange_comparison: Dict[str, Any]) -> str:
    """Generate a template-based summary when ai_summary is not in the JSON."""
    summary_data = analysis.get("summary", {}) or {}
    top_gainers = (analysis.get("top_gainers") or [])[:2]
    top_losers = (analysis.get("top_losers") or [])[:2]

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
        top_gainer = top_gainers[0] or {}
        symbol = top_gainer.get("symbol")
        if symbol is not None and "change_percent" in top_gainer:
            change = _safe_float(top_gainer.get("change_percent"))
            summary_parts.append(
                f"{symbol} led gains with a {change:.2f}% increase."
            )

    if top_losers:
        top_loser = top_losers[0] or {}
        symbol = top_loser.get("symbol")
        if symbol is not None and "change_percent" in top_loser:
            change = _safe_float(top_loser.get("change_percent"))
            summary_parts.append(
                f"{symbol} declined {abs(change):.2f}%, "
                "marking the largest drop."
            )

    items = [
        (name, stats if isinstance(stats, dict) else {})
        for name, stats in (exchange_comparison or {}).items()
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
        
        # Calculate overall statistics
        total_stocks = len(df)
        gainers = len(df[df['change_percent'] > 0])
        losers = len(df[df['change_percent'] < 0])
        unchanged = len(df[df['change_percent'] == 0])
        
        avg_change = float(df['change_percent'].mean())
        max_change = float(df['change_percent'].max())
        min_change = float(df['change_percent'].min())
        
        # Calculate per-index statistics
        indices = {}
        if 'index_name' in df.columns:
            for index_name in df['index_name'].unique():
                index_df = df[df['index_name'] == index_name]
                indices[index_name.replace(' ', '')] = IndexData(
                    stocks=len(index_df),
                    avgChange=float(index_df['change_percent'].mean()),
                    gainers=len(index_df[index_df['change_percent'] > 0]),
                    losers=len(index_df[index_df['change_percent'] < 0])
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
        
        # Filter by sign first so a large limit cannot mix gainers into losers
        # (or vice versa) when fewer matching movers exist than `limit`.
        if type == "gainers":
            sorted_df = df[df['change_percent'] > 0].nlargest(limit, 'change_percent')
        else:
            sorted_df = df[df['change_percent'] < 0].nsmallest(limit, 'change_percent')
        
        movers = []
        for _, row in sorted_df.iterrows():
            movers.append(StockMover(
                symbol=row['symbol'],
                name=row.get('name', row['symbol']),
                price=float(row['close']),
                change=float(row['change']),
                changePercent=float(row['change_percent']),
                volume=int(row.get('volume', 0))
            ))
        
        return MoversResponse(type=type, data=movers)
    
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


async def get_market_summary():
    """Get market summary (AI-generated if available, otherwise demo summary)."""
    try:
        loader = get_data_loader()
        summary_data = loader.load_summary()
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    ai_summary: Optional[str] = summary_data.get("ai_summary")
    date_str: str = summary_data.get("date", "")

    if ai_summary and ai_summary.strip():
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
