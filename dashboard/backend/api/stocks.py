"""
Stocks API endpoints
"""
import math
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from dashboard.backend.models.stock import StockDetail, CurrentData, ProjectionData, TechnicalData, HistoricalData, HistoricalPoint
from dashboard.backend.services.data_loader import get_data_loader
from datetime import datetime, timedelta

router = APIRouter()


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


@router.get("/{symbol}", response_model=StockDetail)
async def get_stock_detail(symbol: str = Path(..., description="Stock symbol")):
    """Get detailed information for a specific stock"""
    try:
        loader = get_data_loader()
        date = loader.get_latest_date()
        
        if not date:
            raise HTTPException(status_code=404, detail="No data available")
        
        # Load daily data
        daily_df = loader.load_daily_data()
        stock_daily = daily_df[daily_df['symbol'] == symbol.upper()]
        
        if stock_daily.empty:
            raise HTTPException(status_code=404, detail="Stock not found.")
        
        stock_row = stock_daily.iloc[0]
        for col in ("close", "change", "change_percent"):
            if col not in stock_row.index:
                raise HTTPException(status_code=404, detail="Stock not found.")

        price = _finite_float(stock_row["close"])
        change = _finite_float(stock_row["change"])
        change_percent = _finite_float(stock_row["change_percent"])
        if price is None or change is None or change_percent is None:
            raise HTTPException(status_code=404, detail="Stock not found.")

        # Build current data
        volume_raw = stock_row.get("volume", 0)
        try:
            volume = int(float(volume_raw)) if volume_raw is not None and math.isfinite(float(volume_raw)) else 0
        except (TypeError, ValueError):
            volume = 0
        market_cap = None
        if "market_cap" in stock_row.index:
            market_cap = _finite_float(stock_row.get("market_cap"))

        current_data = CurrentData(
            price=price,
            change=change,
            changePercent=change_percent,
            volume=volume,
            marketCap=market_cap
        )
        
        # Try to load projection data
        projection_data = None
        technical_data = None
        
        try:
            proj_df = loader.load_projections()
            stock_proj = proj_df[proj_df['symbol'] == symbol.upper()]
            
            if not stock_proj.empty:
                proj_row = stock_proj.iloc[0]
                
                # Calculate target date
                proj_date = datetime.strptime(date, "%Y-%m-%d")
                target_date = (proj_date + timedelta(days=5)).strftime("%Y-%m-%d")
                
                projection_data = ProjectionData(
                    targetDate=target_date,
                    targetPrice=float(proj_row['target_mid']),
                    expectedChange=float(proj_row['expected_change_percent']),
                    confidence=int(proj_row['confidence']),
                    recommendation=proj_row['recommendation'],
                    risk=proj_row['risk_level'],
                    trend=proj_row['trend']
                )
                
                # Build technical data if available
                technical_data = TechnicalData(
                    momentum=float(proj_row.get('momentum_score', 0)) if 'momentum_score' in proj_row else None,
                    volatility=float(proj_row.get('volatility_score', 0)) if 'volatility_score' in proj_row else None,
                    rsi=None  # Not available in current data
                )
        
        except Exception:
            # No projection data available
            pass
        
        return StockDetail(
            symbol=symbol.upper(),
            name=stock_row.get('name', symbol.upper()),
            currentData=current_data,
            projection=projection_data,
            technical=technical_data
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/{symbol}/historical", response_model=HistoricalData)
async def get_stock_historical(
    symbol: str = Path(..., description="Stock symbol"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history")
):
    """Get historical data for a specific stock"""
    try:
        loader = get_data_loader()
        historical_records = loader.load_historical_data(symbol.upper(), days)
        
        if not historical_records:
            raise HTTPException(status_code=404, detail="No historical data found.")
        
        historical_points = []
        for record in historical_records:
            close = _finite_float(record.get("close"))
            change = _finite_float(record.get("change_percent"))
            if close is None or change is None:
                # Skip corrupt/partial days so one bad row cannot 500 the series.
                continue

            proj = record.get('projection')
            # Convert to camelCase for frontend
            projection = None
            if proj:
                projection = {
                    'targetPrice': proj.get('target_price'),
                    'confidence': proj.get('confidence'),
                    'recommendation': proj.get('recommendation'),
                    'expectedChange': proj.get('expected_change'),
                }

            volume_raw = record.get("volume", 0)
            try:
                volume = (
                    int(float(volume_raw))
                    if volume_raw is not None and math.isfinite(float(volume_raw))
                    else 0
                )
            except (TypeError, ValueError):
                volume = 0

            historical_points.append(HistoricalPoint(
                date=record['date'],
                close=close,
                change=change,
                volume=volume,
                projection=projection
            ))

        if not historical_points:
            raise HTTPException(status_code=404, detail="No historical data found.")
        
        return HistoricalData(
            symbol=symbol.upper(),
            data=historical_points
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
