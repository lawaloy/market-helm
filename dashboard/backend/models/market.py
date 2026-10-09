"""
Pydantic models for market data
"""
from pydantic import BaseModel
from typing import Dict, Optional


class IndexData(BaseModel):
    stocks: int
    avgChange: float
    gainers: int
    losers: int


class MarketOverview(BaseModel):
    date: str
    quoteTimeStart: Optional[str] = None
    quoteTimeEnd: Optional[str] = None
    totalStocks: int
    gainers: int
    losers: int
    unchanged: int
    averageChange: float
    maxChange: float
    minChange: float
    indices: Dict[str, IndexData]


class StockMover(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    changePercent: float
    volume: int
    quoteTimestamp: Optional[str] = None


class MoversResponse(BaseModel):
    type: str
    data: list[StockMover]
