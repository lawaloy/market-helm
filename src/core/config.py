"""
MarketHelm - Configuration Module

Handles loading of configuration for indices and exchanges.
"""

import json
import os
from pathlib import Path
from typing import List

# Default indices to track if config not found
_DEFAULT_INDICES = ["S&P 500", "NASDAQ-100"]


def get_indices_to_track() -> List[str]:
    """
    Get list of indices to track from config file.
    
    Returns:
        List of index names (e.g., ["S&P 500", "NASDAQ-100"])
    """
    # Try to find config file (adjust path for new location in core/)
    config_paths = [
        Path(__file__).parent.parent.parent / "config" / "exchanges.json",
        Path("config/exchanges.json"),
        Path(os.getenv("STOCK_TRACKER_CONFIG", "")),
    ]
    
    for config_path in config_paths:
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    break
                indices = config.get("indices_to_track", _DEFAULT_INDICES)
                # A bare string would iterate character-by-character and poison
                # the fetch pipeline; require a list of non-empty strings.
                if not isinstance(indices, list):
                    break
                cleaned = [
                    name.strip()
                    for name in indices
                    if isinstance(name, str) and name.strip()
                ]
                if cleaned:
                    return cleaned
            except Exception:
                # Silent failure - will use defaults
                break
    
    # Return defaults if config file not found
    return _DEFAULT_INDICES

