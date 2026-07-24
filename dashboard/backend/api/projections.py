"""
Projections API endpoints
"""
import math
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from dashboard.backend.models.projection import ProjectionsSummary, OpportunitiesResponse, Opportunity
from dashboard.backend.services.data_loader import get_data_loader
from datetime import datetime, timedelta

router = APIRouter()


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


@router.get("/summary", response_model=ProjectionsSummary)
async def get_projections_summary():
    """Get projections summary with statistics"""
    try:
        loader = get_data_loader()
        date = loader.get_latest_date()
        
        if not date:
            raise HTTPException(status_code=404, detail="No data available")
        
        # Load projections data
        df = loader.load_projections()
        
        # Calculate target date (5 days from projection date)
        proj_date = datetime.strptime(date, "%Y-%m-%d")
        target_date = (proj_date + timedelta(days=5)).strftime("%Y-%m-%d")
        
        # Calculate statistics
        total_projections = len(df)
        avg_confidence = (
            _safe_float(df['confidence'].mean()) if 'confidence' in df.columns else 0.0
        )
        avg_expected_change = (
            _safe_float(df['expected_change_percent'].mean())
            if 'expected_change_percent' in df.columns
            else 0.0
        )
        
        # Determine sentiment
        if avg_expected_change > 1.0:
            sentiment = "Bullish"
        elif avg_expected_change < -1.0:
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"
        
        # Count recommendations
        recommendations = {}
        if 'recommendation' in df.columns:
            rec_counts = df['recommendation'].value_counts().to_dict()
            recommendations = {
                "STRONG_BUY": rec_counts.get("STRONG BUY", 0),
                "BUY": rec_counts.get("BUY", 0),
                "HOLD": rec_counts.get("HOLD", 0),
                "SELL": rec_counts.get("SELL", 0),
                "STRONG_SELL": rec_counts.get("STRONG SELL", 0)
            }
        
        # Count trends
        trends = {}
        if 'trend' in df.columns:
            trend_counts = df['trend'].value_counts().to_dict()
            trends = {
                "Bullish": trend_counts.get("Bullish", 0),
                "Neutral": trend_counts.get("Neutral", 0),
                "Bearish": trend_counts.get("Bearish", 0)
            }
        
        # Count risk levels
        risk_profile = {}
        if 'risk_level' in df.columns:
            risk_counts = df['risk_level'].value_counts().to_dict()
            risk_profile = {
                "Low": risk_counts.get("Low", 0),
                "Medium": risk_counts.get("Medium", 0),
                "High": risk_counts.get("High", 0)
            }
        
        return ProjectionsSummary(
            date=date,
            targetDate=target_date,
            totalProjections=total_projections,
            averageConfidence=round(avg_confidence, 1),
            expectedMarketMove=round(avg_expected_change, 2),
            sentiment=sentiment,
            recommendations=recommendations,
            trends=trends,
            riskProfile=risk_profile
        )
    
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def get_opportunities(
    type: str = Query("STRONG_BUY", pattern="^(STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL)$"),
    limit: int = Query(10, ge=1, le=50)
):
    """Get top opportunities by recommendation type"""
    try:
        loader = get_data_loader()
        date = loader.get_latest_date()
        
        if not date:
            raise HTTPException(status_code=404, detail="No data available")
        
        # Load projections and daily data
        proj_df = loader.load_projections()
        daily_df = loader.load_daily_data()

        # Missing ranking columns → empty list (not KeyError→500)
        if (
            proj_df is None
            or getattr(proj_df, "empty", False)
            or "recommendation" not in proj_df.columns
            or "confidence" not in proj_df.columns
        ):
            return OpportunitiesResponse(type=type, count=0, opportunities=[])

        # Map type to recommendation string
        rec_map = {
            "STRONG_BUY": "STRONG BUY",
            "BUY": "BUY",
            "HOLD": "HOLD",
            "SELL": "SELL",
            "STRONG_SELL": "STRONG SELL"
        }
        
        # Filter by recommendation
        filtered_df = proj_df[proj_df['recommendation'] == rec_map[type]]
        
        # Sort by confidence score
        sorted_df = filtered_df.nlargest(limit, 'confidence')
        
        opportunities = []
        for _, row in sorted_df.iterrows():
            symbol = row['symbol']
            
            # Get current price from daily data
            stock_daily = daily_df[daily_df['symbol'] == symbol]
            current_price = float(stock_daily.iloc[0]['close']) if not stock_daily.empty else 0
            volume = int(stock_daily.iloc[0].get('volume', 0)) if not stock_daily.empty else 0
            
            opportunities.append(Opportunity(
                symbol=symbol,
                name=row.get('name', symbol),
                currentPrice=current_price,
                targetPrice=float(row['target_mid']),
                expectedChange=float(row['expected_change_percent']),
                confidence=int(row['confidence']),
                risk=row['risk_level'],
                trend=row['trend'],
                reason=row.get('reason', ''),
                volume=volume,
                momentum=float(row.get('momentum_score', 0)) if 'momentum_score' in row else None,
                volatility=float(row.get('volatility_score', 0)) if 'volatility_score' in row else None
            ))
        
        return OpportunitiesResponse(
            type=type,
            count=len(filtered_df),
            opportunities=opportunities
        )
    
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
