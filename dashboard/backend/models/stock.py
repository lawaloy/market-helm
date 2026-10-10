"""
Pydantic models for stock data
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class CurrentData(BaseModel):
    price: float
    change: float
    changePercent: float
    volume: int
    marketCap: Optional[float] = None


class ProjectionData(BaseModel):
    targetDate: str
    targetPrice: float
    expectedChange: float
    confidence: int
    recommendation: str
    risk: str
    trend: str


class TechnicalData(BaseModel):
    momentum: Optional[float] = None
    volatility: Optional[float] = None
    rsi: Optional[float] = None


class StockDetail(BaseModel):
    symbol: str
    name: str
    currentData: CurrentData
    projection: Optional[ProjectionData] = None
    technical: Optional[TechnicalData] = None


class HistoricalPoint(BaseModel):
    date: str
    close: float
    change: float
    volume: int
    projection: Optional[Dict] = None


class HistoricalData(BaseModel):
    symbol: str
    data: List[HistoricalPoint]
