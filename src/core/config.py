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
    # STOCK_TRACKER_CONFIG must win over the bundled repo config so deploys
    # can override the tracked universe without editing the package tree.
    config_paths: List[Path] = []
    env_raw = (os.getenv("STOCK_TRACKER_CONFIG") or "").strip()
    if env_raw:
        config_paths.append(Path(env_raw))
    config_paths.extend(
        [
            Path(__file__).parent.parent.parent / "config" / "exchanges.json",
            Path("config/exchanges.json"),
        ]
    )

    for config_path in config_paths:
        if not config_path.exists():
            continue
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            if not isinstance(config, dict):
                continue
            indices = config.get("indices_to_track", _DEFAULT_INDICES)
            # A bare string would iterate character-by-character and poison
            # the fetch pipeline; require a list of non-empty strings.
            if not isinstance(indices, list):
                continue
            cleaned = [
                name.strip()
                for name in indices
                if isinstance(name, str) and name.strip()
            ]
            if cleaned:
                return cleaned
        except Exception:
            # Soft-fail this candidate and try the next path (or defaults).
            continue

    # Return defaults if config file not found
    return _DEFAULT_INDICES
