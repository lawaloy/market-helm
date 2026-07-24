"""
MarketHelm - Data Storage Module

Handles saving and loading stock market data to/from CSV files.
"""

import pandas as pd
from ..utils.company_names import enrich_stock_data_with_names
import os
import json
import math
from datetime import datetime, timedelta
from typing import Any, List, Dict, Optional
from pathlib import Path


def _json_safe_value(value: Any) -> Any:
    """Coerce nested non-finite floats to None for strict JSON writers."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return value


def _md_reason(value: Any, max_len: int) -> str:
    """Truncate reason text; None/NaN/non-strings must not raise on slice/len."""
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    # pandas may surface missing cells as NaN floats before string columns.
    if pd.isna(value):
        return ""
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _md_money(value: Any) -> str:
    """Format a money cell; None/NaN/Inf must not raise on :.2f."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"${number:.2f}"


def _md_pct(value: Any, precision: int = 1, signed: bool = True) -> str:
    """Format a percent cell; non-finite values render as an em dash."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    if signed:
        return f"{number:+.{precision}f}%"
    return f"{number:.{precision}f}%"


def _data_date_for_filename() -> datetime.date:
    """Use most recent trading day for filenames. If today is weekend, use last Friday."""
    today = datetime.now().date()
    if today.weekday() == 5:  # Saturday -> Friday
        return today - timedelta(days=1)
    if today.weekday() == 6:  # Sunday -> Friday
        return today - timedelta(days=2)
    return today


class DataStorage:
    """Manages storage of stock market data in CSV format."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize data storage.
        
        Args:
            data_dir: Directory to store data files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
    
    def _get_daily_file_path(self, date: datetime.date = None) -> Path:
        """Get file path for daily data. Uses most recent trading day when date not specified."""
        if date is None:
            date = _data_date_for_filename()
        
        filename = f"daily_data_{date.strftime('%Y-%m-%d')}.csv"
        return self.data_dir / filename
    
    def save_daily_data(self, data: List[Dict], date: datetime.date = None) -> str:
        """
        Save daily stock data to CSV.
        Enriches company names at save time (pytickersymbols) when name==symbol.
        
        Args:
            data: List of stock data dictionaries
            date: Date for the data (defaults to today)
        
        Returns:
            Path to saved file
        """
        if not data:
            return None
        
        enrich_stock_data_with_names(data)
        df = pd.DataFrame(data)
        file_path = self._get_daily_file_path(date)
        df.to_csv(file_path, index=False)
        return str(file_path)
    
    def load_daily_data(self, date: datetime.date = None) -> Optional[pd.DataFrame]:
        """
        Load daily stock data from CSV.
        
        Args:
            date: Date to load (defaults to today)
        
        Returns:
            DataFrame with stock data or None if not found
        """
        file_path = self._get_daily_file_path(date)
        
        if not file_path.exists():
            return None
        
        try:
            return pd.read_csv(file_path)
        except Exception as e:
            print(f"Error loading data from {file_path}: {str(e)}")
            return None
    
    def save_summary(self, summary_data: Dict, date: datetime.date = None) -> str:
        """
        Save daily summary statistics.
        
        Args:
            summary_data: Dictionary with summary statistics
            date: Date for the summary (defaults to today)
        
        Returns:
            Path to saved file
        """
        if date is None:
            date = _data_date_for_filename()
        
        summary_path = self.data_dir / f"summary_{date.strftime('%Y-%m-%d')}.json"
        
        summary_data["date"] = str(date)
        # Default json.dump writes non-standard NaN/Infinity literals; coerce first
        # and refuse allow_nan so dashboard/CLI consumers always get strict JSON.
        payload = _json_safe_value(summary_data)
        with open(summary_path, 'w') as f:
            json.dump(payload, f, indent=2, allow_nan=False)
        
        return str(summary_path)
    
    def save_projections(self, projections: Dict, date: datetime.date = None) -> str:
        """
        Save stock projections to CSV and generate Markdown report.
        
        Args:
            projections: Dictionary of stock projections
            date: Date for the projections (defaults to today)
        
        Returns:
            Path to saved CSV file
        """
        if not projections:
            return None
        
        if date is None:
            date = _data_date_for_filename()
        
        # Convert projections dict to list of dicts for DataFrame
        projection_list = list(projections.values())
        
        df = pd.DataFrame(projection_list)
        
        # Reorder columns for better readability
        column_order = [
            'symbol', 'name', 'current_price', 'target_low', 'target_mid', 'target_high',
            'expected_change_percent', 'recommendation', 'confidence', 'trend',
            'momentum_score', 'volatility_score', 'risk_level', 'reason',
            'projection_date', 'generated_at'
        ]
        
        # Only include columns that exist
        columns = [col for col in column_order if col in df.columns]
        df = df[columns]
        
        # Save CSV
        csv_path = self.data_dir / f"projections_{date.strftime('%Y-%m-%d')}.csv"
        df.to_csv(csv_path, index=False)
        
        # Generate Markdown report
        try:
            md_path = self.data_dir / f"projections_{date.strftime('%Y-%m-%d')}.md"
            self._generate_projection_markdown(df, md_path, date)
        except Exception as e:
            print(f"Warning: Could not generate markdown report: {e}")
        
        return str(csv_path)
    
    def _generate_projection_markdown(self, df: pd.DataFrame, output_path: Path, date: datetime.date):
        """Generate a formatted Markdown report from projections DataFrame."""
        from datetime import datetime
        
        # Parse dates
        projection_date = pd.to_datetime(df['projection_date'].iloc[0]).strftime('%B %d, %Y')
        generated_date = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        
        # Calculate statistics
        total_stocks = len(df)
        avg_confidence = df['confidence'].mean()
        avg_expected_change = df['expected_change_percent'].mean()
        
        # Get counts
        rec_counts = df['recommendation'].value_counts().to_dict()
        trend_counts = df['trend'].value_counts().to_dict()
        risk_counts = df['risk_level'].value_counts().to_dict()
        
        # Filter by recommendation
        strong_buys = df[df['recommendation'] == 'STRONG BUY'].nlargest(10, 'confidence')
        buys = df[df['recommendation'] == 'BUY'].nlargest(10, 'confidence')
        strong_sells = df[df['recommendation'] == 'STRONG SELL'].nlargest(10, 'confidence')
        
        # Top movers
        top_gainers = df.nlargest(10, 'expected_change_percent')
        top_decliners = df.nsmallest(10, 'expected_change_percent')
        
        # High confidence picks
        high_confidence = df[df['confidence'] >= 85].nlargest(10, 'expected_change_percent')
        
        # Build markdown content
        md = []
        md.append("# Stock Market Projections Report")
        md.append("")
        md.append(f"**Projection Period:** 5 Days (Target Date: {projection_date})")
        md.append("")
        md.append(f"**Generated:** {generated_date}")
        md.append("")
        md.append(f"**Total Stocks Analyzed:** {total_stocks}")
        md.append("")
        md.append("---")
        md.append("")
        
        # Executive Summary
        md.append("## Executive Summary")
        md.append("")
        # Means can be NaN when every row is non-finite; avoid :.2f TypeError
        # on None and keep a readable Neutral sentiment fallback.
        conf_text = (
            f"{float(avg_confidence):.1f}%"
            if pd.notna(avg_confidence) and math.isfinite(float(avg_confidence))
            else "—"
        )
        if pd.notna(avg_expected_change) and math.isfinite(float(avg_expected_change)):
            avg_change = float(avg_expected_change)
            direction = f"{'+' if avg_change >= 0 else ''}{avg_change:.2f}%"
            sentiment = (
                "Bullish"
                if avg_change > 0.5
                else "Bearish"
                if avg_change < -0.5
                else "Neutral"
            )
        else:
            direction = "—"
            sentiment = "Neutral"

        md.append(f"- **Average Confidence Level:** {conf_text}")
        md.append(f"- **Expected Market Direction:** {direction}")
        md.append(f"- **Market Sentiment:** {sentiment}")
        md.append("")
        
        # Recommendation distribution
        md.append("### Recommendation Distribution")
        md.append("")
        md.append("```text")
        total_recs = sum(rec_counts.values())
        for rec in ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']:
            count = rec_counts.get(rec, 0)
            pct = (count / total_recs * 100) if total_recs > 0 else 0
            bar = '█' * int(pct / 2)
            md.append(f"{rec:12} │ {bar} {count:3d} ({pct:5.1f}%)")
        md.append("```")
        md.append("")
        
        # Trend breakdown
        md.append("### Market Sentiment Breakdown")
        md.append("")
        md.append("| Trend | Count | Percentage |")
        md.append("| ----- | ----- | ---------- |")
        for trend in ['Bullish', 'Neutral', 'Bearish']:
            count = trend_counts.get(trend, 0)
            pct = (count / total_stocks * 100) if total_stocks > 0 else 0
            md.append(f"| {trend} | {count} | {pct:.1f}% |")
        md.append("")
        
        # Risk profile
        md.append("### Risk Profile")
        md.append("")
        md.append("| Risk Level | Count | Percentage |")
        md.append("| ---------- | ----- | ---------- |")
        for risk in ['Low', 'Medium', 'High']:
            count = risk_counts.get(risk, 0)
            pct = (count / total_stocks * 100) if total_stocks > 0 else 0
            md.append(f"| {risk} | {count} | {pct:.1f}% |")
        md.append("")
        md.append("---")
        md.append("")
        
        # Strong Buys
        md.append("## STRONG BUY Opportunities")
        md.append("")
        md.append(f"{len(strong_buys)} stocks identified with STRONG BUY rating")
        md.append("")
        
        if len(strong_buys) > 0:
            md.append("| Symbol | Current → Target | Change | Confidence | Reason |")
            md.append("| ------ | ---------------- | ------ | ---------- | ------ |")
            for _, stock in strong_buys.iterrows():
                reason_short = _md_reason(stock.get("reason"), 55)
                md.append(
                    f"| **{stock['symbol']}** | "
                    f"{_md_money(stock.get('current_price'))} → {_md_money(stock.get('target_mid'))} | "
                    f"{_md_pct(stock.get('expected_change_percent'))} | "
                    f"{stock['confidence']}% | {reason_short} |"
                )
        md.append("")
        md.append("---")
        md.append("")
        
        # Buy Opportunities
        md.append("## BUY Opportunities")
        md.append("")
        md.append(f"{len(buys)} stocks identified with BUY rating")
        md.append("")
        
        if len(buys) > 0:
            md.append("| Symbol | Current | Target | Change | Confidence | Risk |")
            md.append("| ------ | ------- | ------ | ------ | ---------- | ---- |")
            for _, stock in buys.iterrows():
                md.append(
                    f"| **{stock['symbol']}** | {_md_money(stock.get('current_price'))} | "
                    f"{_md_money(stock.get('target_mid'))} | "
                    f"{_md_pct(stock.get('expected_change_percent'))} | "
                    f"{stock['confidence']}% | {stock['risk_level']} |"
                )
        md.append("")
        md.append("---")
        md.append("")
        
        # Strong Sells
        md.append("## STRONG SELL Warnings")
        md.append("")
        md.append(f"{len(strong_sells)} stocks identified with STRONG SELL rating")
        md.append("")
        
        if len(strong_sells) > 0:
            md.append("| Symbol | Current | Target | Change | Confidence | Risk | Reason |")
            md.append("| ------ | ------- | ------ | ------ | ---------- | ---- | ------ |")
            for _, stock in strong_sells.iterrows():
                reason_short = _md_reason(stock.get("reason"), 50)
                md.append(
                    f"| **{stock['symbol']}** | {_md_money(stock.get('current_price'))} | "
                    f"{_md_money(stock.get('target_mid'))} | "
                    f"{_md_pct(stock.get('expected_change_percent'))} | "
                    f"{stock['confidence']}% | {stock['risk_level']} | {reason_short} |"
                )
        md.append("")
        md.append("---")
        md.append("")
        
        # Top Gainers
        md.append("## Top Expected Price Gainers")
        md.append("")
        md.append("Stocks projected to increase the most (regardless of recommendation)")
        md.append("")
        md.append("| Symbol | Current | Target | Expected Gain | Confidence | Recommendation |")
        md.append("| ------ | ------- | ------ | ------------- | ---------- | -------------- |")
        for _, stock in top_gainers.iterrows():
            md.append(
                f"| **{stock['symbol']}** | {_md_money(stock.get('current_price'))} | "
                f"{_md_money(stock.get('target_mid'))} | "
                f"{_md_pct(stock.get('expected_change_percent'))} | "
                f"{stock['confidence']}% | {stock['recommendation']} |"
            )
        md.append("")
        
        # Top Decliners
        md.append("## Top Expected Price Decliners")
        md.append("")
        md.append("Stocks projected to decline the most")
        md.append("")
        md.append("| Symbol | Current | Target | Expected Decline | Confidence | Recommendation |")
        md.append("| ------ | ------- | ------ | ---------------- | ---------- | -------------- |")
        for _, stock in top_decliners.iterrows():
            md.append(
                f"| **{stock['symbol']}** | {_md_money(stock.get('current_price'))} | "
                f"{_md_money(stock.get('target_mid'))} | "
                f"{_md_pct(stock.get('expected_change_percent'))} | "
                f"{stock['confidence']}% | {stock['recommendation']} |"
            )
        md.append("")
        md.append("---")
        md.append("")
        
        # High Confidence Picks
        md.append("## High Confidence Picks (85%+)")
        md.append("")
        md.append(f"{len(high_confidence)} stocks with highest confidence and best upside potential")
        md.append("")
        
        if len(high_confidence) > 0:
            md.append("| Symbol | Current → Target | Expected Change | Confidence | Recommendation | Trend |")
            md.append("| ------ | ---------------- | --------------- | ---------- | -------------- | ----- |")
            for _, stock in high_confidence.iterrows():
                md.append(
                    f"| **{stock['symbol']}** | "
                    f"{_md_money(stock.get('current_price'))} → {_md_money(stock.get('target_mid'))} | "
                    f"{_md_pct(stock.get('expected_change_percent'))} | "
                    f"{stock['confidence']}% | {stock['recommendation']} | {stock['trend']} |"
                )
        md.append("")
        md.append("---")
        md.append("")
        
        # Disclaimer
        md.append("## Disclaimer")
        md.append("")
        md.append("> These projections are for informational purposes only. Not financial advice.")
        md.append(">")
        md.append("> Always conduct your own research and consult with financial advisors.")
        md.append("")
        md.append("---")
        md.append("")
        md.append(f"*Generated on {generated_date} by MarketHelm*")
        
        # Write to file with trailing newline
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md) + '\n')
    
    def get_historical_data(self, start_date: datetime.date = None, 
                          end_date: datetime.date = None) -> pd.DataFrame:
        """
        Load historical data for a date range.
        
        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)
        
        Returns:
            Combined DataFrame with historical data
        """
        if end_date is None:
            end_date = datetime.now().date()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        all_data = []
        current_date = start_date
        
        while current_date <= end_date:
            df = self.load_daily_data(current_date)
            if df is not None and not df.empty:
                all_data.append(df)
            current_date += timedelta(days=1)
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()

