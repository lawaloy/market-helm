"""
MarketHelm - Stock Screener Module

Screens stocks from major indices using flexible scoring system.
Designed for trading automation - finds liquid, active stocks worth tracking.
Uses official APIs (no scraping).
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import time
import json
from ..core.logger import setup_logger
from .api_client import FinnhubClient

logger = setup_logger("stock_screener")


class StockScreener:
    """Screens stocks using flexible scoring system."""
    
    def __init__(self, filters_config: Optional[Dict] = None, api_client: Optional[FinnhubClient] = None):
        """
        Initialize screener with filter configuration.
        
        Args:
            filters_config: Dictionary with filter settings (or None for defaults)
            api_client: Optional FinnhubClient instance (creates new one if not provided)
        """
        # Truthy non-dicts (hand-edited filters.json list/string/number) must not
        # reach scoring paths that subscript filters by string key.
        if not isinstance(filters_config, dict):
            filters_config = None
        self.filters = filters_config or self._get_default_filters()
        if not isinstance(self.filters.get("weights"), dict):
            self.filters = {**self.filters, "weights": self._get_default_filters()["weights"]}
        
        try:
            self.api_client = api_client or FinnhubClient()
            logger.debug("Using Finnhub API for stock screening")
        except ValueError as e:
            logger.error(f"Failed to initialize API client: {e}")
            raise
        
        logger.debug(f"Initialized screener with filters: {self.filters}")
    
    def _get_default_filters(self) -> Dict:
        """Get default filter configuration."""
        return {
            "volume_threshold": 1000000,  # 1M shares/day minimum
            "price_min": 10.0,
            "price_max": 500.0,
            "min_daily_change_pct": 2.0,  # 2% minimum move
            "market_cap_min": 1000000000,  # $1B minimum
            "top_n": 100,  # Top N stocks to select
            "weights": {
                "volume": 0.30,  # 30% weight
                "price_change": 0.35,  # 35% weight (most important for trading)
                "price_range": 0.15,  # 15% weight
                "market_cap": 0.20,  # 20% weight
            }
        }

    def _safe_top_n(self, default: int = 100) -> int:
        """Coerce filters.top_n to a non-negative int; bad/non-finite → default."""
        raw = self.filters.get("top_n", default) if isinstance(self.filters, dict) else default
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return max(0, int(number))
    
    @staticmethod
    def _finite_number(value: Any, default: float = 0.0) -> float:
        """Coerce to a finite float; non-numeric / NaN / inf → default."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _score_volume(self, volume: int) -> float:
        """Score based on volume (higher = better)."""
        volume = self._finite_number(volume, default=0.0)
        threshold = self.filters["volume_threshold"]
        if volume < threshold:
            return 0.0
        
        # Normalize: 1M = 50 points, 10M+ = 100 points
        if volume >= 10000000:
            return 100.0
        elif volume >= threshold:
            # Linear scale from threshold to 10M
            ratio = (volume - threshold) / (10000000 - threshold)
            return 50.0 + (ratio * 50.0)
        return 0.0
    
    def _score_price_change(self, change_pct: float) -> float:
        """Score based on price change (absolute value, higher = better)."""
        change_pct = self._finite_number(change_pct, default=0.0)
        min_change = self.filters["min_daily_change_pct"]
        abs_change = abs(change_pct)
        
        if abs_change < min_change:
            return 0.0
        
        # Normalize: 2% = 50 points, 10%+ = 100 points
        if abs_change >= 10.0:
            return 100.0
        elif abs_change >= min_change:
            ratio = (abs_change - min_change) / (10.0 - min_change)
            return 50.0 + (ratio * 50.0)
        return 0.0
    
    def _score_price_range(self, price: float) -> float:
        """Score based on price being in optimal range."""
        price = self._finite_number(price, default=0.0)
        min_price = self.filters["price_min"]
        max_price = self.filters["price_max"]
        
        if min_price <= price <= max_price:
            return 100.0
        elif price < min_price:
            # Too cheap (penny stocks) - lower score
            return max(0.0, (price / min_price) * 50.0)
        else:
            # Too expensive - still score but lower
            if price <= max_price * 2:
                ratio = 1.0 - ((price - max_price) / max_price)
                return max(50.0, ratio * 100.0)
            return 0.0
    
    def _score_market_cap(self, market_cap: float) -> float:
        """Score based on market cap (larger = better, but with diminishing returns)."""
        market_cap = self._finite_number(market_cap, default=0.0)
        min_cap = self.filters["market_cap_min"]
        
        if market_cap < min_cap:
            return 0.0
        
        # Normalize: $1B = 50 points, $100B+ = 100 points
        if market_cap >= 100000000000:  # $100B
            return 100.0
        elif market_cap >= min_cap:
            # Logarithmic scale (diminishing returns)
            ratio = math.log10(market_cap / min_cap) / math.log10(100)  # log base 100
            return 50.0 + min(50.0, ratio * 50.0)
        return 0.0
    
    def calculate_score(self, stock_data: Dict) -> float:
        """
        Calculate total score for a stock based on all filters.
        
        Args:
            stock_data: Dictionary with stock information
        
        Returns:
            Total score (0-100)
        """
        weights = self.filters["weights"]
        
        volume = self._finite_number(stock_data.get("volume", 0), default=0.0)
        change_percent = self._finite_number(
            stock_data.get("change_percent", 0), default=0.0
        )
        close = self._finite_number(stock_data.get("close", 0), default=0.0)

        # Get individual scores
        volume_score = self._score_volume(volume)
        price_change_score = self._score_price_change(change_percent)
        price_range_score = self._score_price_range(close)
        
        # Market cap might not be in stock_data, try to get it
        market_cap = self._finite_number(stock_data.get("market_cap", 0), default=0.0)
        if market_cap == 0:
            # Try to estimate from price and volume, or set default
            market_cap = close * volume * 10  # Rough estimate
        market_cap_score = self._score_market_cap(market_cap)
        
        # Weighted sum
        total_score = (
            volume_score * weights["volume"] +
            price_change_score * weights["price_change"] +
            price_range_score * weights["price_range"] +
            market_cap_score * weights["market_cap"]
        )
        
        return total_score
    
    def screen_stock(self, symbol: str) -> Optional[Dict]:
        """
        Screen a single stock and return data with score using official API.
        Uses lightweight method (1 API call instead of 3) for efficiency.
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            Dictionary with stock data and score, or None if fetch fails
        """
        try:
            # Use lightweight method - only 1 API call (quote only)
            stock_data = self.api_client.get_stock_data_for_screening(symbol)
            
            if not stock_data:
                return None

            # Non-finite core quote fields cannot be ranked meaningfully.
            close = self._finite_number(stock_data.get("close"), default=float("nan"))
            if not math.isfinite(close) or close <= 0:
                return None
            
            # Calculate score (market_cap will be 0, but that's OK for screening)
            # We'll get full data later for qualified stocks
            score = self.calculate_score(stock_data)
            stock_data["screener_score"] = score
            
            return stock_data
            
        except Exception as e:
            logger.debug(f"Error screening {symbol}: {str(e)}")
            return None
    
    def screen_indices(self, index_symbols: List[str], max_workers: int = 10) -> List[Dict]:
        """
        Screen multiple stocks from indices using parallel processing.
        Rate limiter is thread-safe and handles 60 calls/min limit automatically.
        
        Args:
            index_symbols: List of stock symbols to screen
            max_workers: Number of parallel workers (default: 10)
        
        Returns:
            List of stock data dictionaries with scores, sorted by score
        """
        logger.info(f"Screening {len(index_symbols)} stocks in parallel ({max_workers} workers)...")
        screened_stocks = []
        completed = 0
        
        # Use fewer workers to avoid initial burst overwhelming rate limits
        # 60 calls/min = 1 call/sec, so 2 workers is safest for free tier
        optimal_workers = min(max_workers, 2)
        
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            # Submit all screening tasks with slight staggering
            future_to_symbol = {}
            for i, symbol in enumerate(index_symbols):
                # Stagger every 10 submissions to avoid burst
                if i > 0 and i % 10 == 0:
                    time.sleep(0.2)
                future_to_symbol[executor.submit(self.screen_stock, symbol)] = symbol
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                completed += 1
                
                if completed % 50 == 0:
                    logger.info(f"  Screening progress: {completed}/{len(index_symbols)}...")
                    # Batch pause to stay under minute budget
                    time.sleep(5)
                
                try:
                    stock_data = future.result()
                    if stock_data and stock_data.get("screener_score", 0) > 0:
                        screened_stocks.append(stock_data)
                except Exception as e:
                    logger.debug(f"Error screening {symbol}: {e}")
        
        # Sort by score (highest first)
        screened_stocks.sort(key=lambda x: x["screener_score"], reverse=True)
        
        # Take top N (coerce bad top_n from hand-edited filters.json)
        top_n = self._safe_top_n(default=100)
        top_stocks = screened_stocks[:top_n]
        
        logger.info(f"Screened {len(screened_stocks)} qualified stocks, selected top {len(top_stocks)}")
        
        return top_stocks
    
    def get_qualified_symbols(self, index_symbols: List[str], max_workers: int = 10) -> List[str]:
        """
        Get list of qualified stock symbols (without full data).
        Faster for initial screening using parallel processing.
        
        Args:
            index_symbols: List of stock symbols to screen
            max_workers: Number of parallel workers (default: 10)
        
        Returns:
            List of qualified symbols
        """
        screened = self.screen_indices(index_symbols, max_workers=max_workers)
        return [stock["symbol"] for stock in screened]

