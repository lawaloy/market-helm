"""
MarketHelm - Data Analyzer Module

Analyzes stock market data and generates summaries.
"""

import math
import pandas as pd
from typing import Any, Dict, List
from datetime import datetime


def _finite_float(value: Any, default: float = 0.0) -> float:
    """Coerce aggregates to a finite float for JSON-safe summary output."""
    try:
        if value is None:
            return default
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


class StockAnalyzer:
    """Analyzes stock market data and generates insights."""
    
    def analyze_daily_data(self, data: List[Dict]) -> Dict:
        """
        Analyze daily stock data and generate summary statistics.
        
        Args:
            data: List of stock data dictionaries
        
        Returns:
            Dictionary with analysis results
        """
        if not data:
            return {}
        
        df = pd.DataFrame(data)

        # Coerce ranking/count columns so NaN/inf Finnhub or CSV cells cannot
        # inflate leaderboards or leave gainer/loser/unchanged counts inconsistent.
        change = pd.to_numeric(df['change_percent'], errors='coerce')
        volume = pd.to_numeric(df['volume'], errors='coerce')
        close = pd.to_numeric(df['close'], errors='coerce')
        finite_change = change.map(
            lambda value: bool(math.isfinite(value)) if pd.notna(value) else False
        )
        finite_volume = volume.map(
            lambda value: bool(math.isfinite(value)) if pd.notna(value) else False
        )
        scored = df.loc[finite_change].copy()
        scored['_change'] = change.loc[finite_change]
        scored['_close'] = close.loc[finite_change].map(
            lambda value: _finite_float(value, default=0.0)
        )
        volume_ranked = df.loc[finite_volume].copy()
        volume_ranked['_volume'] = volume.loc[finite_volume]
        volume_ranked['_change'] = change.loc[finite_volume].map(
            lambda value: _finite_float(value, default=0.0)
        )
        
        # Overall statistics
        total_stocks = len(df)
        gainers = int((scored['_change'] > 0).sum())
        losers = int((scored['_change'] < 0).sum())
        unchanged = int((scored['_change'] == 0).sum())
        
        # Top gainers and losers (finite change_percent only)
        top_gainers = [
            {
                'symbol': row['symbol'],
                'name': row['name'],
                'change_percent': float(row['_change']),
                'close': float(row['_close']),
            }
            for _, row in scored.nlargest(5, '_change').iterrows()
        ]
        
        top_losers = [
            {
                'symbol': row['symbol'],
                'name': row['name'],
                'change_percent': float(row['_change']),
                'close': float(row['_close']),
            }
            for _, row in scored.nsmallest(5, '_change').iterrows()
        ]
        
        # Highest volume (finite volume only)
        top_volume = [
            {
                'symbol': row['symbol'],
                'name': row['name'],
                'volume': int(row['_volume']),
                'change_percent': float(row['_change']),
            }
            for _, row in volume_ranked.nlargest(5, '_volume').iterrows()
        ]
        
        # Exchange breakdown
        if 'exchange_code' in df.columns:
            exchange_df = df.copy()
            exchange_df['_change'] = change.map(
                lambda value: _finite_float(value, default=float('nan'))
            )
            exchange_df['_volume'] = volume.map(
                lambda value: _finite_float(value, default=0.0)
            )
            exchange_grouped = exchange_df.groupby('exchange_code').agg({
                '_change': ['mean', 'count'],
                '_volume': 'sum'
            }).round(2)
            # Convert MultiIndex columns to JSON-serializable format
            exchange_stats = {}
            for exchange_code in exchange_grouped.index:
                exchange_stats[exchange_code] = {
                    'avg_change_percent': _finite_float(
                        exchange_grouped.loc[exchange_code, ('_change', 'mean')]
                    ),
                    'stock_count': int(exchange_grouped.loc[exchange_code, ('_change', 'count')]),
                    'total_volume': int(
                        _finite_float(
                            exchange_grouped.loc[exchange_code, ('_volume', 'sum')],
                            default=0.0,
                        )
                    ),
                }
        else:
            exchange_stats = {}
        
        # Price statistics — coerce non-finite means/extrema so summary JSON stays valid.
        avg_change = _finite_float(scored['_change'].mean() if len(scored) else 0.0)
        max_change = _finite_float(scored['_change'].max() if len(scored) else 0.0)
        min_change = _finite_float(scored['_change'].min() if len(scored) else 0.0)
        
        return {
            'date': datetime.now().date().isoformat(),
            'summary': {
                'total_stocks': int(total_stocks),
                'gainers': int(gainers),
                'losers': int(losers),
                'unchanged': int(unchanged),
                'average_change_percent': round(avg_change, 2),
                'max_change_percent': round(max_change, 2),
                'min_change_percent': round(min_change, 2),
            },
            'top_gainers': top_gainers,
            'top_losers': top_losers,
            'top_volume': top_volume,
            'exchange_statistics': exchange_stats,
        }
    
    def compare_exchanges(self, exchange_data: Dict[str, List[Dict]]) -> Dict:
        """
        Compare performance across different exchanges.
        
        Args:
            exchange_data: Dictionary mapping exchange codes to their data
        
        Returns:
            Comparison statistics
        """
        comparison = {}
        
        for exchange_code, data in exchange_data.items():
            if not data:
                continue
            
            df = pd.DataFrame(data)
            avg_change = df['change_percent'].mean()
            total_volume = df['volume'].sum()
            
            comparison[exchange_code] = {
                'stock_count': len(df),
                'average_change_percent': round(avg_change, 2),
                'total_volume': int(total_volume),
                'gainers': len(df[df['change_percent'] > 0]),
                'losers': len(df[df['change_percent'] < 0]),
            }
        
        return comparison

