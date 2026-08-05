"""
MarketHelm - Data Analyzer Module

Analyzes stock market data and generates summaries.
"""

import math
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.utils.tickers import normalize_ticker


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


_INVALID_EXCHANGE_SENTINELS = frozenset({"nan", "none", "<na>", "null"})


def _display_name(raw: Any, symbol: str) -> str:
    """Return a JSON-safe display name; fall back to symbol when missing/dirty."""
    if raw is None:
        return symbol
    if isinstance(raw, float) and not math.isfinite(raw):
        return symbol
    try:
        if pd.isna(raw):
            return symbol
    except (TypeError, ValueError):
        pass
    try:
        text = str(raw).strip()
    except Exception:
        return symbol
    if not text or text.lower() in {"nan", "none", "<na>", "null"}:
        return symbol
    return text


def _exchange_stat_key(raw: Any) -> Optional[str]:
    """Return a JSON-safe exchange_statistics key, or None when the label is unusable."""
    if raw is None:
        return None
    if isinstance(raw, float) and not math.isfinite(raw):
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass
    try:
        text = str(raw)
    except Exception:
        return None
    # Keep "" (schema drift) but drop sentinel labels that stringify to "nan"/etc.
    if text.strip().lower() in _INVALID_EXCHANGE_SENTINELS:
        return None
    return text


def _leaderboard_rows(frame: pd.DataFrame, sort_col: str, *, ascending: bool = False, limit: int = 5):
    """Yield ranked rows, over-fetching so blank/sentinel symbols can be skipped."""
    if frame.empty or sort_col not in frame.columns:
        return
    take = min(len(frame), max(limit * 5, limit))
    ordered = (
        frame.nsmallest(take, sort_col) if ascending else frame.nlargest(take, sort_col)
    )
    for _, row in ordered.iterrows():
        yield row


def _leaderboard_identity(row: Any) -> Optional[tuple[str, str]]:
    """Return (symbol, name) for a leaderboard row, or None when symbol is unusable."""
    symbol = normalize_ticker(row.get("symbol") if hasattr(row, "get") else None)
    if not symbol:
        return None
    name = _display_name(row.get("name") if hasattr(row, "get") else None, symbol)
    return symbol, name


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

        # Partial fetch rows / schema drift can omit ranking columns entirely.
        # Ensure them before subscript so analyze soft-returns zeros instead of KeyError.
        for column in ("change_percent", "volume", "close"):
            if column not in df.columns:
                df[column] = float("nan")

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
        
        # Top gainers and losers (finite change_percent only).
        # Missing name/symbol columns previously KeyError'd the whole day analysis;
        # NaN names also poison summary JSON (allow_nan=False on save).
        top_gainers = []
        for row in _leaderboard_rows(scored, "_change", limit=5):
            identity = _leaderboard_identity(row)
            if identity is None:
                continue
            symbol, name = identity
            top_gainers.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "change_percent": float(row["_change"]),
                    "close": float(row["_close"]),
                }
            )
            if len(top_gainers) >= 5:
                break

        top_losers = []
        for row in _leaderboard_rows(scored, "_change", ascending=True, limit=5):
            identity = _leaderboard_identity(row)
            if identity is None:
                continue
            symbol, name = identity
            top_losers.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "change_percent": float(row["_change"]),
                    "close": float(row["_close"]),
                }
            )
            if len(top_losers) >= 5:
                break

        # Highest volume (finite volume only)
        top_volume = []
        for row in _leaderboard_rows(volume_ranked, "_volume", limit=5):
            identity = _leaderboard_identity(row)
            if identity is None:
                continue
            symbol, name = identity
            top_volume.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "volume": int(row["_volume"]),
                    "change_percent": float(row["_change"]),
                }
            )
            if len(top_volume) >= 5:
                break
        
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
                label = _exchange_stat_key(exchange_code)
                if label is None:
                    continue
                exchange_stats[label] = {
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
        
        # Price statistics ΓÇö coerce non-finite means/extrema so summary JSON stays valid.
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
            # Partial / dirty exchange batches must soft-return zeros instead of
            # KeyError (missing columns) or OverflowError (Inf volume → int()).
            for column in ("change_percent", "volume"):
                if column not in df.columns:
                    df[column] = float("nan")

            change = pd.to_numeric(df["change_percent"], errors="coerce")
            volume = pd.to_numeric(df["volume"], errors="coerce")
            finite_change = change.map(
                lambda value: bool(math.isfinite(value)) if pd.notna(value) else False
            )
            finite_volume = volume.map(
                lambda value: bool(math.isfinite(value)) if pd.notna(value) else False
            )
            usable_change = change[finite_change]
            usable_volume = volume[finite_volume]

            avg_change = _finite_float(
                usable_change.mean() if len(usable_change) else 0.0
            )
            total_volume = _finite_float(
                usable_volume.sum() if len(usable_volume) else 0.0
            )

            comparison[exchange_code] = {
                'stock_count': len(df),
                'average_change_percent': round(avg_change, 2),
                'total_volume': int(total_volume),
                'gainers': int((usable_change > 0).sum()) if len(usable_change) else 0,
                'losers': int((usable_change < 0).sum()) if len(usable_change) else 0,
            }
        
        return comparison

