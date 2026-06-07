"""
Send alert events via SMTP email (stdlib only).
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Union

from ...core.logger import setup_logger

logger = setup_logger("alerts.email")


def _parse_recipients(value: Union[str, List[str], None]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class EmailNotifier:
    """Deliver alert events as plain-text email."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        to_addrs: List[str],
        from_addr: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._to_addrs = to_addrs
        self._from_addr = from_addr or username
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._timeout = timeout

    @classmethod
    def from_alert(cls, alert: Dict[str, Any]) -> Optional["EmailNotifier"]:
        host = alert.get("smtp_host") or os.environ.get("SMTP_HOST")
        port_raw = alert.get("smtp_port") or os.environ.get("SMTP_PORT", "587")
        username = alert.get("smtp_user") or os.environ.get("SMTP_USER")
        password = alert.get("smtp_password") or os.environ.get("SMTP_PASSWORD")
        to_addrs = _parse_recipients(alert.get("email_to")) or _parse_recipients(
            os.environ.get("ALERT_EMAIL_TO")
        )
        from_addr = alert.get("email_from") or os.environ.get("ALERT_EMAIL_FROM") or username

        if not host or not str(host).strip():
            logger.warning(
                "Email notifier requested but SMTP_HOST is missing: set 'smtp_host' on the alert "
                "or SMTP_HOST in the environment."
            )
            return None
        if not username or not password:
            logger.warning(
                "Email notifier requested but SMTP credentials are missing: set SMTP_USER and "
                "SMTP_PASSWORD (or per-alert smtp_user / smtp_password)."
            )
            return None
        if not to_addrs:
            logger.warning(
                "Email notifier requested but no recipients: set 'email_to' on the alert "
                "or ALERT_EMAIL_TO in the environment."
            )
            return None

        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            logger.warning("Invalid SMTP port %r; expected an integer.", port_raw)
            return None

        use_ssl = _env_bool("SMTP_USE_SSL") or port == 465
        use_tls = not use_ssl and (_env_bool("SMTP_USE_TLS", default=port == 587))

        return cls(
            host=str(host).strip(),
            port=port,
            username=str(username).strip(),
            password=str(password),
            to_addrs=to_addrs,
            from_addr=str(from_addr).strip() if from_addr else None,
            use_tls=use_tls,
            use_ssl=use_ssl,
        )

    def _format_message(self, event: Dict[str, Any]) -> EmailMessage:
        symbols = ", ".join(event.get("symbols") or []) or "(none)"
        subject = f"MarketHelm alert: {event.get('alert_name', event.get('alert_id', 'alert'))}"
        body = "\n".join(
            [
                f"Alert: {event.get('alert_name', event.get('alert_id', 'alert'))}",
                f"ID: {event.get('alert_id', '')}",
                f"Symbols: {symbols}",
                f"Condition: {event.get('condition_type', '')}",
                f"Time (UTC): {event.get('timestamp', '')}",
                "",
                "— MarketHelm",
            ]
        )
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._from_addr
        message["To"] = ", ".join(self._to_addrs)
        message.set_content(body)
        return message

    def send(self, event: Dict[str, Any]) -> bool:
        message = self._format_message(event)
        try:
            if self._use_ssl:
                with smtplib.SMTP_SSL(
                    self._host, self._port, timeout=self._timeout
                ) as smtp:
                    smtp.login(self._username, self._password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                    if self._use_tls:
                        smtp.starttls()
                    smtp.login(self._username, self._password)
                    smtp.send_message(message)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "Email delivery failed for alert %s: %s",
                event.get("alert_id"),
                exc,
            )
            return False
