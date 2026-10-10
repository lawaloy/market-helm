"""Backward compatibility for names used before the MarketHelm rename.

The project was renamed from ``market-helm`` to ``markethelm``. Existing installs keep working:

* Environment variables: ``MARKETHELM_*`` is canonical. A deprecated ``MARKET_HELM_*`` variable
  is still honoured when the new name is unset or empty (the new name always wins), and a
  one-time deprecation warning is logged per variable.
* User config directory: ``~/.markethelm`` is canonical. If only ``~/.market-helm`` (or the
  older ``~/.market-desk``) exists it is renamed to ``~/.markethelm``; if the rename fails
  (for example the folder is in use) the legacy folder keeps being used so nothing is lost.

Remove this module once the deprecation window has passed.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Set

_logger = logging.getLogger(__name__)

NEW_ENV_PREFIX = "MARKETHELM_"
LEGACY_ENV_PREFIX = "MARKET_HELM_"
_warned: Set[str] = set()


def legacy_env_name(name: str) -> Optional[str]:
    """Deprecated ``MARKET_HELM_*`` spelling of a canonical ``MARKETHELM_*`` name."""
    if name.startswith(NEW_ENV_PREFIX):
        suffix = name.removeprefix(NEW_ENV_PREFIX)
        return LEGACY_ENV_PREFIX + suffix
    return None


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """``os.environ.get`` that also accepts the deprecated ``MARKET_HELM_*`` spelling."""
    value = os.environ.get(name)
    if value:
        return value
    legacy = legacy_env_name(name)
    if legacy is not None:
        legacy_value = os.environ.get(legacy)
        if legacy_value:
            if legacy not in _warned:
                _warned.add(legacy)
                _logger.warning(
                    "Environment variable %s is deprecated; rename it to %s", legacy, name
                )
            return legacy_value
    return value if value is not None else default


def resolve_user_config_dir(home: Path) -> Path:
    """Return ``~/.markethelm``, migrating ``~/.market-helm`` / ``~/.market-desk`` if needed."""
    dest = home / ".markethelm"
    if dest.exists():
        return dest
    for legacy_name in (".market-helm", ".market-desk"):
        legacy = home / legacy_name
        if not legacy.exists():
            continue
        try:
            legacy.rename(dest)
        except OSError as exc:
            _logger.warning(
                "Could not rename ~/%s to ~/.markethelm (%s); continuing to use ~/%s",
                legacy_name,
                exc,
                legacy_name,
            )
            return legacy
        _logger.info("Migrated user config: ~/%s -> ~/.markethelm", legacy_name)
        return dest
    return dest
