"""CLI: market-helm alerts list|test|init"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..alerts.alert_engine import AlertEngine
from ..alerts.alert_paths import init_user_alerts_config, resolve_alerts_config_path
from ..core.logger import setup_logger

logger = setup_logger()


def _load_config(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_condition(condition: Dict[str, Any]) -> str:
    ctype = condition.get("type", "?")
    if ctype == "price_threshold":
        return (
            f"{condition.get('symbol')} {condition.get('operator')} "
            f"{condition.get('value')}"
        )
    if ctype == "screening_match":
        filters = condition.get("filters", {})
        parts = [f"{key}={value}" for key, value in filters.items()]
        return "screening: " + ", ".join(parts)
    return ctype


def _find_alert(alerts: List[Dict[str, Any]], alert_id: str) -> Optional[Dict[str, Any]]:
    for alert in alerts:
        if alert.get("id") == alert_id:
            return alert
    return None


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    from ..alerts.alert_paths import user_config_dir

    load_dotenv()
    user_env = user_config_dir() / ".env"
    if user_env.exists():
        load_dotenv(user_env, override=True)


def cmd_list(config_path: Optional[Path] = None) -> int:
    path = resolve_alerts_config_path(config_path)
    if not path.exists():
        logger.error(
            "No alerts config at %s. Run: market-helm alerts init",
            path,
        )
        return 1

    config = _load_config(path)
    alerts = config.get("alerts", [])
    if not alerts:
        logger.info("No alert rules in %s", path)
        return 0

    logger.info("Alerts config: %s", path)
    logger.info("-" * 60)
    for alert in alerts:
        enabled = alert.get("enabled", False)
        status = "enabled" if enabled else "disabled"
        notifications = ", ".join(alert.get("notifications") or ["log"])
        condition = _format_condition(alert.get("condition", {}))
        logger.info(
            "%s  [%s]  %s",
            alert.get("id", "?"),
            status,
            alert.get("name", alert.get("id", "?")),
        )
        logger.info("  condition: %s", condition)
        logger.info("  notify: %s", notifications)
        if alert.get("webhook_format") or alert.get("payload_format"):
            logger.info(
                "  webhook format: %s",
                alert.get("webhook_format") or alert.get("payload_format"),
            )
        logger.info("")
    return 0


def cmd_init(force: bool = False) -> int:
    try:
        dest = init_user_alerts_config(force=force)
    except FileExistsError:
        from ..alerts.alert_paths import user_config_dir

        logger.error(
            "%s already exists. Use --force to overwrite.",
            user_config_dir() / "alerts.json",
        )
        return 1
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Created %s", dest)
    logger.info("Edit the file, set enabled rules to true, and configure SMTP/webhook env vars.")
    logger.info("Secrets (SMTP password, webhook URLs) belong in ~/.market-helm/.env — not in git.")
    return 0


def cmd_test(alert_id: str, dry_run: bool = False, config_path: Optional[Path] = None) -> int:
    path = resolve_alerts_config_path(config_path)
    if not path.exists():
        logger.error("No alerts config at %s. Run: market-helm alerts init", path)
        return 1

    config = _load_config(path)
    alert = _find_alert(config.get("alerts", []), alert_id)
    if alert is None:
        logger.error("No alert with id %r in %s", alert_id, path)
        return 1

    event = {
        "alert_id": alert["id"],
        "alert_name": alert.get("name", alert["id"]),
        "symbols": ["TEST"],
        "timestamp": datetime.utcnow().isoformat(),
        "condition_type": alert.get("condition", {}).get("type", "test"),
        "test": True,
    }

    engine = AlertEngine([alert])
    notifiers = engine._build_notifiers(alert)
    if not notifiers:
        logger.error("No notifiers configured for alert %r", alert_id)
        return 1

    logger.info("Testing alert %r (%s)", alert_id, "dry-run" if dry_run else "live")
    for notifier in notifiers:
        name = notifier.__class__.__name__
        if dry_run:
            payload = event
            if hasattr(notifier, "build_payload"):
                payload = notifier.build_payload(event)
            logger.info("[%s] would send: %s", name, json.dumps(payload, indent=2))
        else:
            notifier.send(event)
            logger.info("[%s] sent test notification", name)
    return 0


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="market-helm alerts",
        description="Manage MarketHelm alert rules (config + test notifications)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to alerts.json (default: ~/.market-helm/alerts.json or repo config)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List configured alert rules")

    init_parser = sub.add_parser("init", help="Create ~/.market-helm/alerts.json from the bundled example")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing user alerts file",
    )

    test_parser = sub.add_parser("test", help="Send a test notification for one rule (no market check)")
    test_parser.add_argument("--id", required=True, help="Alert id from alerts.json")
    test_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads instead of delivering notifications",
    )

    args = parser.parse_args(argv)
    _load_env()

    if args.command == "list":
        sys.exit(cmd_list(args.config))
    if args.command == "init":
        sys.exit(cmd_init(force=args.force))
    if args.command == "test":
        sys.exit(cmd_test(args.id, dry_run=args.dry_run, config_path=args.config))
