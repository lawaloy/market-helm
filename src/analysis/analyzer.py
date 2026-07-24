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


def _finite_mask(series: pd.Series) -> pd.Series:
    """True where values coerce to a finite float (excludes NaN/inf)."""
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.apply(lambda value: bool(math.isfinite(value)) if pd.notna(value) else False)


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
        
        # Overall statistics
        total_stocks = len(df)
        gainers = len(df[df['change_percent'] > 0])
        losers = len(df[df['change_percent'] < 0])
        unchanged = len(df[df['change_percent'] == 0])
        
        # Top gainers/losers/volume — skip non-finite rows so summary JSON stays valid.
        change_ok = df[_finite_mask(df["change_percent"])]
        top_gainers = change_ok.nlargest(5, "change_percent")[
            ["symbol", "name", "change_percent", "close"]
        ].to_dict("records")

        top_losers = change_ok.nsmallest(5, "change_percent")[
            ["symbol", "name", "change_percent", "close"]
        ].to_dict("records")

        volume_ok = df[_finite_mask(df["volume"])]
        top_volume = volume_ok.nlargest(5, "volume")[
            ["symbol", "name", "volume", "change_percent"]
        ].to_dict("records")
        for row in top_volume:
            row["change_percent"] = _finite_float(row.get("change_percent"))
            row["volume"] = int(_finite_float(row.get("volume")))
        for row in top_gainers + top_losers:
            row["change_percent"] = _finite_float(row.get("change_percent"))
            row["close"] = _finite_float(row.get("close"))
        
        # Exchange breakdown
        if 'exchange_code' in df.columns:
            exchange_grouped = df.groupby('exchange_code').agg({
                'change_percent': ['mean', 'count'],
                'volume': 'sum'
            }).round(2)
            # Convert MultiIndex columns to JSON-serializable format
            exchange_stats = {}
            for exchange_code in exchange_grouped.index:
                exchange_stats[exchange_code] = {
                    'avg_change_percent': _finite_float(
                        exchange_grouped.loc[exchange_code, ('change_percent', 'mean')]
                    ),
                    'stock_count': int(exchange_grouped.loc[exchange_code, ('change_percent', 'count')]),
                    'total_volume': int(
                        _finite_float(
                            exchange_grouped.loc[exchange_code, ('volume', 'sum')],
                            default=0.0,
                        )
                    ),
                }
        else:
            exchange_stats = {}
        
        # Price statistics — coerce non-finite means/extrema so summary JSON stays valid.
        avg_change = _finite_float(df['change_percent'].mean())
        max_change = _finite_float(df['change_percent'].max())
        min_change = _finite_float(df['change_percent'].min())
        
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

