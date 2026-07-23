"""Alerts settings API — read/write user alert config and send test notifications."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dashboard.backend.auth import require_user_id
from src.storage.database import database_enabled
from src.storage.user_alerts import (
    init_user_alerts_config,
    load_user_alerts_config,
    save_user_alerts_config,
)

from src.alerts.alert_paths import (
    init_minimal_user_alerts_config,
    load_alerts_config,
    polish_alerts_config,
    save_alerts_config,
    strip_webhook_secrets_from_config,
    update_user_env_vars,
    user_alerts_config_path,
    user_config_dir,
)
from src.alerts.notifiers.email_delivery import email_delivery_configured
from src.cli.alerts_commands import _load_env, run_alert_test

from dashboard.backend.api.history import build_symbol_catalog
from dashboard.backend.services.data_loader import get_data_loader
from src.alerts.symbol_prices import prices_from_saved_daily_data, resolve_symbol_prices
from src.storage.alert_watches import InvalidAlertWatchConfig

router = APIRouter()


class AlertsStatusResponse(BaseModel):
    checks_on_fetch: bool = True
    last_data_date: Optional[str] = None
    tracked_symbols: List[str] = Field(default_factory=list)
    active_watches: int = 0
    last_triggered_at: Optional[str] = None
    latest_deliveries: List[Dict[str, Any]] = Field(default_factory=list)


class AlertsRunResponse(BaseModel):
    triggered: int
    last_data_date: Optional[str] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)
    message: Optional[str] = None


class AlertDefaults(BaseModel):
    email_to: Optional[str] = None
    webhook_url: Optional[str] = None  # write-only: saved to ~/.market-helm/.env, never returned
    webhook_format: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_webhook: Optional[bool] = None


class AlertsConfigBody(BaseModel):
    defaults: Optional[AlertDefaults] = None
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class ChannelStatus(BaseModel):
    email_smtp: bool
    email_recipients: bool
    webhook_url: bool


class AlertsConfigResponse(BaseModel):
    exists: bool
    config: AlertsConfigBody
    channels: ChannelStatus


class AlertInitResponse(BaseModel):
    message: str


class AlertTestRequest(BaseModel):
    id: str
    dry_run: bool = False


class AlertTestResponse(BaseModel):
    alert_id: str
    status: str
    notifiers: List[str]
    previews: Optional[List[Dict[str, Any]]] = None


class SymbolQuotesRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)


class SymbolQuotesResponse(BaseModel):
    prices: Dict[str, float] = Field(default_factory=dict)


def _empty_config() -> Dict[str, Any]:
    return {"defaults": {}, "alerts": []}


def _normalize_config(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not raw:
        return _empty_config()
    alerts = raw.get("alerts")
    if not isinstance(alerts, list):
        raise HTTPException(status_code=400, detail="Config must include an 'alerts' array.")
    defaults = dict(raw.get("defaults") or {})
    webhook_format = defaults.get("webhook_format")
    if isinstance(webhook_format, str):
        defaults["webhook_format"] = webhook_format.strip().lower()
    return {"defaults": defaults, "alerts": alerts}


def _has_webhook_secret(config: Dict[str, Any]) -> bool:
    defaults = config.get("defaults") or {}
    if str(defaults.get("webhook_url") or "").strip():
        return True
    return any(
        isinstance(alert, dict) and str(alert.get("webhook_url") or "").strip()
        for alert in config.get("alerts") or []
    )


def _channel_status(
    config: Dict[str, Any],
    *,
    has_webhook_secret: Optional[bool] = None,
) -> ChannelStatus:
    defaults = config.get("defaults") or {}
    has_rule_email = any(alert.get("email_to") for alert in config.get("alerts", []))
    has_default_email = bool(defaults.get("email_to") or os.environ.get("ALERT_EMAIL_TO"))
    if database_enabled():
        webhook_ready = bool(has_webhook_secret)
    else:
        webhook_ready = bool(
            has_webhook_secret
            if has_webhook_secret is not None
            else _has_webhook_secret(config)
        ) or bool(os.environ.get("ALERT_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK_URL"))
    return ChannelStatus(
        email_smtp=email_delivery_configured(),
        email_recipients=has_default_email or has_rule_email,
        webhook_url=webhook_ready,
    )


def _public_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Config safe to send to the browser — no webhook URLs."""
    return strip_webhook_secrets_from_config(config)


def _persist_webhook_secret(defaults: Optional[AlertDefaults]) -> None:
    if defaults is None:
        return
    updates: Dict[str, str] = {}
    if defaults.webhook_url and defaults.webhook_url.strip():
        updates["DISCORD_WEBHOOK_URL"] = defaults.webhook_url.strip()
    if defaults.webhook_format and defaults.webhook_format.strip():
        updates["ALERT_WEBHOOK_FORMAT"] = defaults.webhook_format.strip().lower()
    if updates:
        update_user_env_vars(updates)


def _load_raw_config(user_id: Optional[str]) -> tuple[bool, Optional[Dict[str, Any]]]:
    if database_enabled():
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return load_user_alerts_config(user_id)
    path = user_alerts_config_path()
    if not path.exists():
        return False, None
    _, raw = load_alerts_config(path)
    return raw is not None, raw


def _save_raw_config(user_id: Optional[str], config: Dict[str, Any]) -> None:
    if database_enabled():
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        try:
            save_user_alerts_config(user_id, config)
        except InvalidAlertWatchConfig as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return
    save_alerts_config(config)


@router.get("/config", response_model=AlertsConfigResponse)
async def get_alerts_config(
    user_id: Optional[str] = Depends(require_user_id),
) -> AlertsConfigResponse:
    """Return the user alerts config and channel readiness (no secrets)."""
    _load_env()
    exists, raw = _load_raw_config(user_id)
    if raw is not None:
        raw = polish_alerts_config(raw)
        if not database_enabled():
            scrubbed = strip_webhook_secrets_from_config(raw)
            if scrubbed != raw:
                save_alerts_config(scrubbed)
                raw = scrubbed
    has_webhook_secret = _has_webhook_secret(raw or {})
    config = _public_config(_normalize_config(raw))
    defaults = dict(config.get("defaults") or {})
    if not defaults.get("webhook_format"):
        env_format = (os.environ.get("ALERT_WEBHOOK_FORMAT") or "").strip().lower()
        if env_format in {"discord", "slack", "json"}:
            defaults["webhook_format"] = env_format
        elif os.environ.get("DISCORD_WEBHOOK_URL"):
            defaults["webhook_format"] = "discord"
    config["defaults"] = defaults
    return AlertsConfigResponse(
        exists=exists,
        config=AlertsConfigBody(**config),
        channels=_channel_status(config, has_webhook_secret=has_webhook_secret),
    )


@router.put("/config", response_model=AlertsConfigResponse)
async def put_alerts_config(
    body: AlertsConfigBody,
    user_id: Optional[str] = Depends(require_user_id),
) -> AlertsConfigResponse:
    """Save alerts config to the user config path."""
    _load_env()
    if not database_enabled():
        _persist_webhook_secret(body.defaults)
    _load_env()
    config = _normalize_config(body.model_dump())
    for alert in config["alerts"]:
        if not alert.get("id"):
            raise HTTPException(status_code=400, detail="Each alert must have an id.")
    _save_raw_config(user_id, config)
    status_source = config
    if database_enabled() and user_id:
        _, saved = load_user_alerts_config(user_id)
        if saved is not None:
            status_source = saved
    status_source = polish_alerts_config(status_source)
    has_webhook_secret = _has_webhook_secret(status_source)
    public = _public_config(status_source)
    return AlertsConfigResponse(
        exists=True,
        config=AlertsConfigBody(**public),
        channels=_channel_status(public, has_webhook_secret=has_webhook_secret),
    )


@router.post("/init", response_model=AlertInitResponse)
async def post_alerts_init(
    force: bool = False,
    user_id: Optional[str] = Depends(require_user_id),
) -> AlertInitResponse:
    """Create an empty alerts config for onboarding."""
    _load_env()
    if database_enabled():
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        try:
            init_user_alerts_config(user_id, force=force)
        except FileExistsError:
            raise HTTPException(
                status_code=409,
                detail="Alerts config already exists for this user. Pass ?force=true to overwrite.",
            )
        return AlertInitResponse(
            message="Alerts config created. Edit rules in Settings and send a test notification.",
        )
    try:
        init_minimal_user_alerts_config(force=force)
    except FileExistsError:
        raise HTTPException(
            status_code=409,
            detail=f"{user_config_dir() / 'alerts.json'} already exists. Pass ?force=true to overwrite.",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return AlertInitResponse(
        message="Alerts config created. Edit rules in Settings and send a test notification.",
    )


@router.get("/health")
async def alerts_health() -> Dict[str, bool]:
    """Lightweight probe so the UI can detect a stale dashboard backend."""
    return {"ok": True, "quotes": True}


@router.get("/symbols")
async def get_alert_symbol_catalog():
    """Searchable company list for alert setup (major US indices + tracked symbols)."""
    symbols, names = build_symbol_catalog()
    tracked: List[str] = []
    saved_prices = prices_from_saved_daily_data()
    try:
        loader = get_data_loader()
        df = loader.load_projections()
        if not df.empty and "symbol" in df.columns:
            tracked = sorted({str(s).upper() for s in df["symbol"].unique()})
    except (ValueError, Exception):
        pass
    return {
        "symbols": symbols,
        "names": names,
        "count": len(symbols),
        "tracked_symbols": tracked,
        "prices": {symbol: saved_prices[symbol] for symbol in symbols if symbol in saved_prices},
    }


@router.get("/quotes", response_model=SymbolQuotesResponse)
async def get_symbol_quotes(symbols: str = Query("", description="Comma-separated tickers")) -> SymbolQuotesResponse:
    """Latest prices for up to 15 symbols (saved data, then live quotes)."""
    _load_env()
    parsed = [str(symbol).upper() for symbol in symbols.split(",") if str(symbol).strip()][:15]
    if not parsed:
        return SymbolQuotesResponse(prices={})
    return SymbolQuotesResponse(prices=resolve_symbol_prices(parsed, fetch_missing=True))


@router.post("/quotes", response_model=SymbolQuotesResponse)
async def post_symbol_quotes(body: SymbolQuotesRequest) -> SymbolQuotesResponse:
    """Latest prices for up to 15 symbols (saved data, then live quotes)."""
    _load_env()
    symbols = [str(symbol).upper() for symbol in body.symbols if str(symbol).strip()][:15]
    if not symbols:
        return SymbolQuotesResponse(prices={})
    return SymbolQuotesResponse(prices=resolve_symbol_prices(symbols, fetch_missing=True))


@router.get("/status", response_model=AlertsStatusResponse)
async def get_alerts_status(
    user_id: Optional[str] = Depends(require_user_id),
) -> AlertsStatusResponse:
    """Alert status: active watches, last data date, and last trigger time."""
    _load_env()
    tracked: List[str] = []
    last_date: Optional[str] = None
    active_watches = 0
    last_triggered: Optional[str] = None
    latest_deliveries: List[Dict[str, Any]] = []

    try:
        loader = get_data_loader()
        last_date = loader.get_latest_date()
        df = loader.load_projections()
        if not df.empty and "symbol" in df.columns:
            tracked = sorted({str(s).upper() for s in df["symbol"].unique()})
    except (ValueError, Exception):
        pass

    path = user_alerts_config_path()
    if database_enabled():
        if user_id:
            _, raw = load_user_alerts_config(user_id)
            if raw:
                alerts = raw.get("alerts") or []
                active_watches = sum(1 for alert in alerts if alert.get("enabled"))
    elif path.exists():
        _, raw = load_alerts_config(path)
        if raw:
            alerts = raw.get("alerts") or []
            active_watches = sum(1 for alert in alerts if alert.get("enabled"))

    try:
        if database_enabled() and user_id:
            from src.alerts.user_alert_storage import UserAlertStorage

            storage = UserAlertStorage(user_id)
            last_triggered = storage.latest_event_timestamp()
            latest_deliveries = storage.latest_delivery_by_channel()
        else:
            from src.alerts.alert_storage import AlertStorage
            from src.alerts.delivery_status import latest_deliveries_by_channel

            storage = AlertStorage()
            last_triggered = storage.latest_event_timestamp()
            latest_deliveries = latest_deliveries_by_channel(storage)
    except Exception:
        pass

    return AlertsStatusResponse(
        checks_on_fetch=True,
        last_data_date=last_date,
        tracked_symbols=tracked,
        active_watches=active_watches,
        last_triggered_at=last_triggered,
        latest_deliveries=latest_deliveries,
    )


@router.post("/run", response_model=AlertsRunResponse)
async def run_alerts_now(
    user_id: Optional[str] = Depends(require_user_id),
) -> AlertsRunResponse:
    """Evaluate active alerts against saved data and live quotes for watch symbols."""
    try:
        from src.alerts.alert_worker import run_check_once, run_user_check

        raw = run_user_check(user_id) if user_id else run_check_once()
    except Exception:
        raise HTTPException(status_code=500, detail="Alert check failed.")
    if raw.get("message") == "No market data available.":
        raise HTTPException(
            status_code=404,
            detail="No market data available. Add a watch or fetch dashboard data first.",
        )
    return AlertsRunResponse(
        triggered=raw["triggered"],
        last_data_date=raw.get("last_data_date"),
        events=raw.get("events") or [],
        message=raw.get("message"),
    )


@router.post("/test", response_model=AlertTestResponse)
async def post_alert_test(
    body: AlertTestRequest,
    user_id: Optional[str] = Depends(require_user_id),
) -> AlertTestResponse:
    """Send a test notification for one alert rule."""
    _load_env()
    config_payload: Optional[Dict[str, Any]] = None
    storage = None
    if database_enabled():
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        exists, raw = load_user_alerts_config(user_id)
        if not exists or raw is None:
            raise HTTPException(status_code=404, detail="No alerts config for this user.")
        config_payload = raw
        from src.alerts.user_alert_storage import UserAlertStorage

        storage = UserAlertStorage(user_id)
    try:
        result = run_alert_test(
            body.id,
            dry_run=body.dry_run,
            config=config_payload,
            storage=storage,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AlertTestResponse(
        alert_id=result["alert_id"],
        status=result["status"],
        notifiers=result.get("notifiers") or [],
        previews=result.get("previews"),
    )
