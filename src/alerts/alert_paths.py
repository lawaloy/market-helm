"""Resolve alert config locations for repo dev vs pip install (~/.market-helm)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def user_config_dir() -> Path:
    """Per-user config directory (same location as the dashboard uses)."""
    home = Path.home()
    legacy = home / ".market-desk"
    dest = home / ".market-helm"
    if not dest.exists() and legacy.exists():
        try:
            legacy.rename(dest)
        except OSError:
            pass
    return dest


def bundled_example_path() -> Path:
    return _REPO_ROOT / "config" / "alerts.example.json"


def user_alerts_config_path() -> Path:
    """Writable user alerts path (never the repo dev fallback)."""
    env_path = os.environ.get("MARKET_HELM_ALERTS_CONFIG")
    if env_path:
        return Path(env_path)
    return user_config_dir() / "alerts.json"


def resolve_alerts_config_path(explicit: Optional[Path] = None) -> Path:
    """Path to alerts.json: env override, then user file, then repo dev file."""
    if explicit is not None:
        return Path(explicit)
    env_path = os.environ.get("MARKET_HELM_ALERTS_CONFIG")
    if env_path:
        return Path(env_path)
    user_path = user_config_dir() / "alerts.json"
    if user_path.exists():
        return user_path
    repo_path = _REPO_ROOT / "config" / "alerts.json"
    if repo_path.exists():
        return repo_path
    return user_path


_PLACEHOLDER_EMAILS = frozenset(
    {"you@example.com", "alerts@example.com", "backup@example.com"}
)


def _is_placeholder_webhook(url: str) -> bool:
    lowered = url.lower()
    return "example.com" in lowered or "your/webhook" in lowered


def polish_alerts_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Remove bundled placeholders and seed defaults from environment when available."""
    polished = dict(config)
    defaults = dict(polished.get("defaults") or {})

    env_email = (os.environ.get("ALERT_EMAIL_TO") or "").strip()
    if env_email and not defaults.get("email_to"):
        defaults["email_to"] = env_email

    polished["defaults"] = defaults
    alerts: list[Dict[str, Any]] = []
    for alert in polished.get("alerts") or []:
        cleaned = dict(alert)
        email = str(cleaned.get("email_to") or "").strip().lower()
        if email in _PLACEHOLDER_EMAILS:
            cleaned.pop("email_to", None)
        webhook_url = str(cleaned.get("webhook_url") or "").strip()
        if webhook_url and _is_placeholder_webhook(webhook_url):
            cleaned.pop("webhook_url", None)
        alerts.append(cleaned)
    polished["alerts"] = alerts
    return dedupe_alerts_config(polished)


def _price_alert_key(condition: Dict[str, Any]) -> Optional[str]:
    if condition.get("type") != "price_threshold":
        return None
    symbol = condition.get("symbol")
    operator = condition.get("operator")
    value = condition.get("value")
    if not symbol or not operator or value is None:
        return None
    return f"{str(symbol).upper()}|{operator}|{value}"


def dedupe_alerts_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Keep one rule per price-threshold condition (first wins)."""
    seen: set[str] = set()
    unique: list[Dict[str, Any]] = []
    for alert in config.get("alerts") or []:
        key = _price_alert_key(alert.get("condition") or {}) or str(alert.get("id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(alert)
    config["alerts"] = unique
    return config


def init_minimal_user_alerts_config(force: bool = False) -> Path:
    """Create an empty user alerts config with env-based defaults (dashboard onboarding)."""
    dest = user_alerts_config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        raise FileExistsError(str(dest))
    save_alerts_config(polish_alerts_config({"defaults": {}, "alerts": []}), explicit=dest)
    return dest


def init_user_alerts_config(force: bool = False) -> Path:
    """Copy bundled alerts.example.json to the user alerts config path."""
    dest = user_alerts_config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        raise FileExistsError(str(dest))
    example = bundled_example_path()
    if not example.exists():
        raise FileNotFoundError(f"Bundled example not found: {example}")
    shutil.copy(example, dest)
    with open(dest, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    save_alerts_config(polish_alerts_config(config), explicit=dest)
    return dest


def load_alerts_config(explicit: Optional[Path] = None) -> Tuple[Path, Optional[Dict[str, Any]]]:
    """Return resolved config path and parsed JSON, or None if the file is missing."""
    path = resolve_alerts_config_path(explicit) if explicit is None else Path(explicit)
    if not path.exists():
        return path, None
    with open(path, "r", encoding="utf-8") as handle:
        return path, json.load(handle)


def save_alerts_config(config: Dict[str, Any], explicit: Optional[Path] = None) -> Path:
    """Write alerts config atomically to the user config path."""
    path = Path(explicit) if explicit is not None else user_alerts_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = polish_alerts_config(config)
    payload = strip_webhook_secrets_from_config(payload)
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    tmp.replace(path)
    return path


def get_enabled_watch_symbols() -> List[str]:
    """Symbols referenced by enabled price-threshold watches."""
    _, raw = load_alerts_config()
    if not raw:
        return []
    symbols: set[str] = set()
    for alert in raw.get("alerts") or []:
        if not alert.get("enabled"):
            continue
        condition = alert.get("condition") or {}
        if condition.get("type") != "price_threshold":
            continue
        symbol = condition.get("symbol")
        if symbol:
            symbols.add(str(symbol).upper())
    return sorted(symbols)


def apply_alert_defaults(alert: Dict[str, Any], defaults: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge config-level defaults into a rule for notification delivery."""
    if not defaults:
        return alert
    merged = dict(alert)
    notifications = merged.get("notifications") or []
    if "email" in notifications and not merged.get("email_to") and defaults.get("email_to"):
        merged["email_to"] = defaults["email_to"]
    if "webhook" in notifications:
        if not merged.get("webhook_url") and defaults.get("webhook_url"):
            merged["webhook_url"] = defaults["webhook_url"]
        if not merged.get("webhook_format") and defaults.get("webhook_format"):
            merged["webhook_format"] = defaults["webhook_format"]
    return merged


def strip_webhook_secrets_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Remove webhook URLs from persisted config — secrets belong in server env only."""
    cleaned = dict(config)
    defaults = dict(cleaned.get("defaults") or {})
    defaults.pop("webhook_url", None)
    cleaned["defaults"] = defaults
    cleaned["alerts"] = [
        {k: v for k, v in alert.items() if k != "webhook_url"}
        for alert in cleaned.get("alerts") or []
    ]
    return cleaned


def update_user_env_vars(updates: Dict[str, str]) -> None:
    """Update ~/.market-helm/.env without logging or returning secret values."""
    env_path = user_config_dir() / ".env"
    user_config_dir().mkdir(parents=True, exist_ok=True)
    existing: Dict[str, str] = {}
    order: list[str] = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            existing[key] = value.strip()
            if key not in order:
                order.append(key)
    for key, value in updates.items():
        if not value:
            if key in existing:
                del existing[key]
                if key in order:
                    order.remove(key)
            continue
        existing[key] = value
        if key not in order:
            order.append(key)
    content = "\n".join(f"{key}={existing[key]}" for key in order)
    env_path.write_text(f"{content}\n" if content else "", encoding="utf-8")
