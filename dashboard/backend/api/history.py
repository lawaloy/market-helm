"""
Historical trends API endpoints
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from pydantic import BaseModel

from dashboard.backend.services.data_loader import get_data_loader

logger = logging.getLogger(__name__)
router = APIRouter()


def load_index_symbol_names() -> dict:
    """
    Symbol -> company name for major US indices (S&P 500, NASDAQ 100, Dow Jones).
    """
    result = {}
    try:
        from pytickersymbols import PyTickerSymbols

        data = PyTickerSymbols()
        for index_name in ["S&P 500", "NASDAQ 100", "Dow Jones"]:
            try:
                for stock in data.get_stocks_by_index(index_name):
                    sym = stock.get("symbol")
                    name = stock.get("name")
                    if sym and name:
                        result[str(sym).upper()] = name
            except Exception:
                continue
    except Exception:
        pass
    return result


def _resolve_company_names(symbols: list) -> dict:
    """
    Resolve symbol->company name via pytickersymbols (S&P 500, NASDAQ 100, Dow Jones).
    """
    if not symbols:
        return {}
    catalog = load_index_symbol_names()
    return {sym: catalog.get(str(sym).upper(), sym) for sym in symbols}


def build_symbol_catalog() -> tuple:
    """
    Full picker catalog: major US index constituents plus any symbols in latest projections.
    Returns (sorted_symbols, symbol_names).
    """
    names = load_index_symbol_names()
    symbols = set(names.keys())
    try:
        loader = get_data_loader()
        df = loader.load_projections()
        if not df.empty and "symbol" in df.columns:
            name_col = "name" if "name" in df.columns else None
            for sym in df["symbol"].unique():
                sym_key = str(sym).upper()
                symbols.add(sym_key)
                if name_col:
                    stored = df.loc[df["symbol"] == sym, name_col].iloc[0]
                    if stored and str(stored).strip() and str(stored) != sym_key:
                        names[sym_key] = str(stored).strip()
                elif sym_key not in names:
                    names[sym_key] = sym_key
    except (ValueError, Exception):
        pass
    sorted_symbols = sorted(symbols)
    return sorted_symbols, {sym: names.get(sym, sym) for sym in sorted_symbols}


class DailySummaryPoint(BaseModel):
    """Summary for a single day"""
    date: str
    totalProjections: int
    averageConfidence: float
    expectedMarketMove: float
    sentiment: str
    strongBuy: int
    buy: int
    hold: int
    sell: int
    strongSell: int


class HistoricalSummaryResponse(BaseModel):
    """Aggregated historical summary"""
    dates: List[str]
    data: List[DailySummaryPoint]
    firstDate: str
    lastDate: str
    symbols: List[str] = []
    names: dict = {}


class AccuracySample(BaseModel):
    """One evaluated projection vs actual close."""

    symbol: str
    runDate: str
    targetDate: str
    actualDate: str
    predicted: float
    actual: float
    absErrorPct: float
    recommendation: str


class AccuracySummary(BaseModel):
    """Rollups for projection accuracy."""

    sampleCount: int
    meanAbsErrorPct: Optional[float] = None
    byRecommendation: dict = {}


class ProjectionAccuracyResponse(BaseModel):
    """Projection accuracy over the lookback window."""

    summary: AccuracySummary
    samples: List[AccuracySample]


@router.get("/dates")
async def get_available_dates():
    """Get list of all available dates with data"""
    try:
        loader = get_data_loader()
        dates = loader.get_available_dates()
        return {"dates": dates}
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/symbols")
async def get_tracked_symbols():
    """Get list of all tracked stock symbols (from latest projections)"""
    try:
        loader = get_data_loader()
        date = loader.get_latest_date()
        if not date:
            raise HTTPException(status_code=404, detail="No data available")

        df = loader.load_projections()
        symbols, symbol_names = build_symbol_catalog()
        if not symbols:
            symbols = df['symbol'].unique().tolist() if 'symbol' in df.columns else []
            symbol_names = _resolve_company_names(symbols)

        return {
            "symbols": symbols,
            "names": symbol_names,
            "date": date,
        }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/summary")
async def get_historical_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days of history")
):
    """Get aggregated projections summary over time"""
    try:
        loader = get_data_loader()
        dates = loader.get_available_dates()
        if not dates:
            raise HTTPException(status_code=404, detail="No data available")

        dates_to_load = dates[:days]
        symbols_list = []
        symbol_names = {}  # Populated from projections CSV when name column has real names

        data_points = []
        for date in dates_to_load:
            try:
                df = loader.load_projections(date)
                if df.empty:
                    continue

                total = len(df)
                avg_confidence = float(df['confidence'].mean()) if 'confidence' in df.columns else 0
                avg_expected = float(df['expected_change_percent'].mean()) if 'expected_change_percent' in df.columns else 0

                if avg_expected > 1.0:
                    sentiment = "Bullish"
                elif avg_expected < -1.0:
                    sentiment = "Bearish"
                else:
                    sentiment = "Neutral"

                rec_counts = df['recommendation'].value_counts().to_dict() if 'recommendation' in df.columns else {}
                strong_buy = rec_counts.get("STRONG BUY", 0)
                buy = rec_counts.get("BUY", 0)
                hold = rec_counts.get("HOLD", 0)
                sell = rec_counts.get("SELL", 0)
                strong_sell = rec_counts.get("STRONG SELL", 0)

                data_points.append(DailySummaryPoint(
                    date=date,
                    totalProjections=total,
                    averageConfidence=round(avg_confidence, 1),
                    expectedMarketMove=round(avg_expected, 2),
                    sentiment=sentiment,
                    strongBuy=strong_buy,
                    buy=buy,
                    hold=hold,
                    sell=sell,
                    strongSell=strong_sell,
                ))
                # Extract symbols and names from first successful load (latest data)
                if not symbols_list and 'symbol' in df.columns:
                    symbols_list = sorted(df['symbol'].unique().tolist())
                    if 'name' in df.columns:
                        symbol_names = df.drop_duplicates('symbol')[['symbol', 'name']].set_index('symbol')['name'].to_dict()
            except Exception:
                continue

        first_date = dates_to_load[-1] if dates_to_load else ""
        last_date = dates_to_load[0] if dates_to_load else ""

        # Resolve company names: use stored names from CSV when real, else pytickersymbols
        resolved = _resolve_company_names(symbols_list)
        for sym in symbols_list:
            stored = symbol_names.get(sym)
            if stored and stored != sym:
                resolved[sym] = stored  # Prefer CSV/stored names over lookup
        symbol_names = resolved

        return {
            "dates": dates_to_load,
            "data": [p.model_dump() for p in data_points],
            "firstDate": first_date,
            "lastDate": last_date,
            "symbols": symbols_list,
            "names": symbol_names,
        }

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/accuracy", response_model=ProjectionAccuracyResponse)
async def get_projection_accuracy(
    days: int = Query(90, ge=7, le=365, description="Look back this many days of projection runs"),
):
    """
    Compare each run's target_mid to the first available actual close on/after the target date.
    Requires overlapping daily_data and projections files across time.
    """
    try:
        loader = get_data_loader()
        raw = loader.compute_projection_accuracy(days)
        return ProjectionAccuracyResponse(
            summary=AccuracySummary(**raw["summary"]),
            samples=[AccuracySample(**s) for s in raw["samples"]],
        )
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
