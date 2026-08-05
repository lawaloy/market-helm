"""
Pydantic models for projection data
"""
from pydantic import BaseModel
from typing import Dict, Optional


class ProjectionsSummary(BaseModel):
    date: str
    targetDate: str
    totalProjections: int
    averageConfidence: float
    expectedMarketMove: float
    sentiment: str
    recommendations: Dict[str, int]
    trends: Dict[str, int]
    riskProfile: Dict[str, int]


class Opportunity(BaseModel):
    symbol: str
    name: str
    currentPrice: float
    targetPrice: float
    expectedChange: float
    confidence: int
    risk: str
    trend: str
    reason: str
    volume: int
    # Default keeps concurrent Opportunity(...) constructors valid until callers
    # start passing recommendation explicitly (dashboard table filters need it).
    recommendation: str = ""
    momentum: Optional[float] = None
    volatility: Optional[float] = None


class OpportunitiesResponse(BaseModel):
    type: str
    count: int
    opportunities: list[Opportunity]
