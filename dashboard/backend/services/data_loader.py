"""
Data loading service for reading CSV and JSON files
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import json
from datetime import datetime, timedelta
from functools import lru_cache


def _default_data_dir() -> Path:
    """Resolve data directory: DATA_DIR env, repo data/ when developing, else ~/.stock-exchange-tracker/data."""
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    here = Path(__file__).resolve()
    if "site-packages" in here.parts:
        return Path.home() / ".stock-exchange-tracker" / "data"
    # Project root is 4 levels up (dashboard/backend/services/data_loader.py)
    project_root = here.parent.parent.parent.parent
    return project_root / "data"


def _is_weekday(date_str: str) -> bool:
    """True if date (YYYY-MM-DD) is Mon–Fri (stock market open)."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.weekday() < 5  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    except ValueError:
        return True  # Keep if we can't parse


def get_most_recent_trading_day() -> str:
    """Return the most recent trading day (YYYY-MM-DD). If today is weekend, returns last Friday."""
    today = datetime.now().date()
    # weekday: Mon=0, Fri=4, Sat=5, Sun=6
    if today.weekday() == 5:  # Saturday -> Friday
        today = today - timedelta(days=1)
    elif today.weekday() == 6:  # Sunday -> Friday
        today = today - timedelta(days=2)
    return today.strftime("%Y-%m-%d")


class DataLoader:
    """Loads and caches stock market data from CSV/JSON files"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            self.data_dir = _default_data_dir()
        else:
            self.data_dir = Path(data_dir).resolve()
        
        if not self.data_dir.exists():
            raise ValueError(f"Data directory not found: {self.data_dir}")
    
    def _get_latest_file(self, pattern: str, sort_by_date: bool = False) -> Optional[Path]:
        """Get the most recent file matching the pattern.
        When sort_by_date=True, uses date in filename (YYYY-MM-DD) for daily_data/projections/summary.
        """
        files = list(self.data_dir.glob(pattern))
        if not files:
            return None
        if sort_by_date:
            # Extract date from filename (e.g. daily_data_2026-02-14.csv) and pick latest
            def parse_date(f: Path) -> str:
                stem = f.stem
                if "daily_data_" in stem:
                    return stem.replace("daily_data_", "")
                if "projections_" in stem:
                    return stem.replace("projections_", "")
                if "summary_" in stem:
                    return stem.replace("summary_", "")
                return ""
            dated = [(f, parse_date(f)) for f in files if parse_date(f)]
            if not dated:
                return max(files, key=lambda f: f.stat().st_mtime)
            dated.sort(key=lambda x: x[1], reverse=True)
            # Prefer most recent trading day (weekday); market closed Sat/Sun
            for f, d in dated:
                if _is_weekday(d):
                    return f
            return dated[0][0]  # Fallback to most recent if all weekends
        return max(files, key=lambda f: f.stat().st_mtime)

    def get_latest_date(self) -> Optional[str]:
        """Get the date of the most recent trading-day data (skips weekends when market is closed)."""
        dates = self.get_available_dates()
        for d in dates:
            if _is_weekday(d):
                return d
        return dates[0] if dates else None

    def needs_fetch_for_latest_trading_day(self) -> bool:
        """True if we don't have data for the most recent trading day (e.g. last Friday)."""
        target = get_most_recent_trading_day()
        dates = self.get_available_dates()
        return target not in dates
    
    def load_daily_data(self, date: Optional[str] = None) -> pd.DataFrame:
        """Load daily stock data CSV"""
        if date is None:
            file_path = self._get_latest_file("daily_data_*.csv", sort_by_date=True)
            if file_path is None:
                raise ValueError("No daily data files found")
        else:
            file_path = self.data_dir / f"daily_data_{date}.csv"
            if not file_path.exists():
                raise ValueError(f"Daily data file not found for date: {date}")
        
        df = pd.read_csv(file_path)
        return df
    
    def load_projections(self, date: Optional[str] = None) -> pd.DataFrame:
        """Load projections CSV"""
        if date is None:
            file_path = self._get_latest_file("projections_*.csv", sort_by_date=True)
            if file_path is None:
                raise ValueError("No projection files found")
        else:
            file_path = self.data_dir / f"projections_{date}.csv"
            if not file_path.exists():
                raise ValueError(f"Projections file not found for date: {date}")
        
        df = pd.read_csv(file_path)
        return df
    
    def load_summary(self, date: Optional[str] = None) -> Dict:
        """Load summary JSON"""
        if date is None:
            file_path = self._get_latest_file("summary_*.json", sort_by_date=True)
            if file_path is None:
                raise ValueError("No summary files found")
        else:
            file_path = self.data_dir / f"summary_{date}.json"
            if not file_path.exists():
                raise ValueError(f"Summary file not found for date: {date}")
        
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def get_available_dates(self) -> List[str]:
        """Get list of all available dates"""
        files = list(self.data_dir.glob("daily_data_*.csv"))
        dates = [f.stem.replace("daily_data_", "") for f in files]
        return sorted(dates, reverse=True)
    
    def load_historical_data(self, symbol: str, days: int = 30) -> List[Dict]:
        """Load historical data for a specific symbol"""
        dates = self.get_available_dates()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        historical_data = []
        for date in dates:
            if date < cutoff_date:
                break
            
            try:
                # Load daily data
                daily_df = self.load_daily_data(date)
                stock_data = daily_df[daily_df['symbol'] == symbol]
                
                if stock_data.empty:
                    continue
                
                stock_record = stock_data.iloc[0].to_dict()
                
                # Try to load projections for this date
                try:
                    proj_df = self.load_projections(date)
                    proj_data = proj_df[proj_df['symbol'] == symbol]
                    
                    if not proj_data.empty:
                        proj_record = proj_data.iloc[0].to_dict()
                        stock_record['projection'] = {
                            'target_price': proj_record.get('target_mid', None),
                            'confidence': proj_record.get('confidence', None),
                            'recommendation': proj_record.get('recommendation', None),
                            'expected_change': proj_record.get('expected_change_percent', None)
                        }
                except Exception:
                    # No projection data for this date
                    pass
                
                stock_record['date'] = date
                historical_data.append(stock_record)
            
            except Exception:
                continue
        
        return historical_data

    @staticmethod
    def _projection_target_date(row: Dict[str, Any], run_date: str) -> str:
        """Target calendar date for the 5-day price target (from CSV or run date + 5 days)."""
        raw = row.get("projection_date")
        if raw is not None and str(raw).strip():
            try:
                return datetime.strptime(str(raw)[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                pass
        rd = datetime.strptime(run_date, "%Y-%m-%d")
        return (rd + timedelta(days=5)).strftime("%Y-%m-%d")

    def get_actual_close_on_or_after(
        self, symbol: str, target_date: str
    ) -> Optional[Tuple[str, float]]:
        """First available daily close for symbol on or after target_date."""
        sym = symbol.upper()
        for d in sorted(self.get_available_dates()):
            if d < target_date:
                continue
            try:
                daily_df = self.load_daily_data(d)
                stock_data = daily_df[daily_df["symbol"] == sym]
                if stock_data.empty:
                    continue
                return d, float(stock_data.iloc[0]["close"])
            except Exception:
                continue
        return None

    def compute_projection_accuracy(self, days: int = 90) -> Dict[str, Any]:
        """
        Compare projected target_mid to actual close on/after the projection target date.
        Only includes rows where the target date is not after our latest daily data.
        """
        dates = self.get_available_dates()
        if not dates:
            return {
                "summary": {
                    "sampleCount": 0,
                    "meanAbsErrorPct": None,
                    "byRecommendation": {},
                },
                "samples": [],
            }

        latest = max(dates)
        cutoff = (datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        run_dates = [d for d in dates if d >= cutoff]

        samples: List[Dict[str, Any]] = []
        for run_date in run_dates:
            try:
                proj_df = self.load_projections(run_date)
            except Exception:
                continue
            if proj_df.empty:
                continue

            for _, row in proj_df.iterrows():
                row_dict = row.to_dict()
                symbol = str(row_dict.get("symbol", "")).upper()
                if not symbol:
                    continue
                try:
                    predicted = float(row_dict["target_mid"])
                except (KeyError, TypeError, ValueError):
                    continue
                if predicted <= 0:
                    continue

                target_date = self._projection_target_date(row_dict, run_date)
                if target_date > latest:
                    continue

                actual = self.get_actual_close_on_or_after(symbol, target_date)
                if not actual:
                    continue
                actual_date, actual_close = actual
                abs_err_pct = abs(actual_close - predicted) / predicted * 100.0
                rec = str(row_dict.get("recommendation", "UNKNOWN") or "UNKNOWN")

                samples.append(
                    {
                        "symbol": symbol,
                        "runDate": run_date,
                        "targetDate": target_date,
                        "actualDate": actual_date,
                        "predicted": round(predicted, 4),
                        "actual": round(actual_close, 4),
                        "absErrorPct": round(abs_err_pct, 3),
                        "recommendation": rec,
                    }
                )

        by_rec: Dict[str, Dict[str, float]] = {}
        for s in samples:
            rec = s["recommendation"]
            if rec not in by_rec:
                by_rec[rec] = {"count": 0, "sumAbs": 0.0}
            by_rec[rec]["count"] += 1
            by_rec[rec]["sumAbs"] += s["absErrorPct"]

        by_recommendation: Dict[str, Dict[str, Any]] = {}
        for rec, agg in by_rec.items():
            c = agg["count"]
            by_recommendation[rec] = {
                "count": c,
                "meanAbsErrorPct": round(agg["sumAbs"] / c, 3) if c else None,
            }

        mean_abs: Optional[float] = None
        if samples:
            mean_abs = round(sum(s["absErrorPct"] for s in samples) / len(samples), 3)

        return {
            "summary": {
                "sampleCount": len(samples),
                "meanAbsErrorPct": mean_abs,
                "byRecommendation": by_recommendation,
            },
            "samples": samples[:300],
        }


# Singleton instance with caching
_data_loader = None


def get_data_loader() -> DataLoader:
    """Get the singleton DataLoader instance"""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader
