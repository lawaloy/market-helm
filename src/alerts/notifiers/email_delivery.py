"""
Transactional email delivery backends for alert notifications.

Supports SMTP (dev / self-host / SES SMTP relay), SendGrid, and Mailgun.
Provider is selected via ALERT_EMAIL_PROVIDER or inferred from env secrets.
"""

from __future__ import annotations

import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Union

import requests

from ...core.logger import setup_logger
from .delivery_retry import DeliveryAttempt, deliver_with_retry, is_retriable_http_status

logger = setup_logger("alerts.email.delivery")

SUPPORTED_PROVIDERS = frozenset({"smtp", "sendgrid", "mailgun"})


def parse_recipients(value: Union[str, List[str], None]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_email_provider() -> str:
    explicit = (os.environ.get("ALERT_EMAIL_PROVIDER") or "").strip().lower()
    if explicit:
        if explicit not in SUPPORTED_PROVIDERS:
            logger.warning(
                "Unknown ALERT_EMAIL_PROVIDER=%r; supported: %s. Falling back to auto-detect.",
                explicit,
                ", ".join(sorted(SUPPORTED_PROVIDERS)),
            )
        else:
            return explicit

    if os.environ.get("SENDGRID_API_KEY"):
        return "sendgrid"
    if os.environ.get("MAILGUN_API_KEY") and os.environ.get("MAILGUN_DOMAIN"):
        return "mailgun"
    return "smtp"


def email_delivery_configured() -> bool:
    """True when the active provider has enough env config to send email."""
    provider = resolve_email_provider()
    if provider == "sendgrid":
        return bool(os.environ.get("SENDGRID_API_KEY") and _platform_from_address())
    if provider == "mailgun":
        return bool(
            os.environ.get("MAILGUN_API_KEY")
            and os.environ.get("MAILGUN_DOMAIN")
            and _platform_from_address()
        )
    return bool(
        os.environ.get("SMTP_HOST")
        and os.environ.get("SMTP_USER")
        and os.environ.get("SMTP_PASSWORD")
    )


def format_alert_email(event: Dict[str, Any]) -> tuple[str, str]:
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
    return subject, body


def _platform_from_address(alert: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if alert:
        from_alert = alert.get("email_from")
        if from_alert and str(from_alert).strip():
            return str(from_alert).strip()
    from_env = os.environ.get("ALERT_EMAIL_FROM")
    if from_env and from_env.strip():
        return from_env.strip()
    if resolve_email_provider() == "smtp":
        if alert:
            smtp_user = alert.get("smtp_user")
            if smtp_user and str(smtp_user).strip():
                return str(smtp_user).strip()
        username = os.environ.get("SMTP_USER")
        if username and str(username).strip():
            return str(username).strip()
    return None


def _resolve_recipients(alert: Dict[str, Any]) -> List[str]:
    """Resolve To: addresses, preferring per-alert recipients.

    Hosted multi-user mode must not fall back to process-wide ``ALERT_EMAIL_TO``
    (mirrors webhook ``_allow_env_webhook`` isolation). Opt in with
    ``_allow_env_email=True`` when intentionally using the shared env mailbox.
    """
    from src.storage.database import database_enabled

    allow_env_email = alert.get("_allow_env_email", not database_enabled()) is not False
    env_recipients = (
        parse_recipients(os.environ.get("ALERT_EMAIL_TO")) if allow_env_email else []
    )
    return parse_recipients(alert.get("email_to")) or env_recipients


class EmailDeliveryBackend(ABC):
    @abstractmethod
    def send(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> bool:
        ...


class SmtpEmailBackend(EmailDeliveryBackend):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._timeout = timeout

    def _send_once(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> DeliveryAttempt:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_addr
        message["To"] = ", ".join(to_addrs)
        message.set_content(body)
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
            return DeliveryAttempt(ok=True)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "SMTP email delivery failed for alert %s: %s",
                event.get("alert_id"),
                exc,
            )
            return DeliveryAttempt(ok=False, retriable=True)

    def send(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> bool:
        return deliver_with_retry(
            operation="SMTP email",
            alert_id=event.get("alert_id"),
            attempt=lambda: self._send_once(
                subject=subject,
                body=body,
                from_addr=from_addr,
                to_addrs=to_addrs,
                event=event,
            ),
        )


class SendGridEmailBackend(EmailDeliveryBackend):
    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def _send_once(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> DeliveryAttempt:
        payload = {
            "personalizations": [{"to": [{"email": addr} for addr in to_addrs]}],
            "from": {"email": from_addr},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        try:
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            if response.status_code in (200, 202):
                return DeliveryAttempt(ok=True)
            logger.warning(
                "SendGrid email delivery failed for alert %s: HTTP %s %s",
                event.get("alert_id"),
                response.status_code,
                response.text[:500],
            )
            return DeliveryAttempt(
                ok=False,
                retriable=is_retriable_http_status(response.status_code),
            )
        except requests.RequestException as exc:
            logger.warning(
                "SendGrid email delivery failed for alert %s: %s",
                event.get("alert_id"),
                exc,
            )
            return DeliveryAttempt(ok=False, retriable=True)

    def send(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> bool:
        return deliver_with_retry(
            operation="SendGrid email",
            alert_id=event.get("alert_id"),
            attempt=lambda: self._send_once(
                subject=subject,
                body=body,
                from_addr=from_addr,
                to_addrs=to_addrs,
                event=event,
            ),
        )


class MailgunEmailBackend(EmailDeliveryBackend):
    def __init__(
        self,
        api_key: str,
        domain: str,
        api_base: str = "https://api.mailgun.net",
        timeout: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._domain = domain
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    def _send_once(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> DeliveryAttempt:
        url = f"{self._api_base}/v3/{self._domain}/messages"
        data = {
            "from": from_addr,
            "to": to_addrs,
            "subject": subject,
            "text": body,
        }
        try:
            response = requests.post(
                url,
                auth=("api", self._api_key),
                data=data,
                timeout=self._timeout,
            )
            if response.status_code in (200, 202):
                return DeliveryAttempt(ok=True)
            logger.warning(
                "Mailgun email delivery failed for alert %s: HTTP %s %s",
                event.get("alert_id"),
                response.status_code,
                response.text[:500],
            )
            return DeliveryAttempt(
                ok=False,
                retriable=is_retriable_http_status(response.status_code),
            )
        except requests.RequestException as exc:
            logger.warning(
                "Mailgun email delivery failed for alert %s: %s",
                event.get("alert_id"),
                exc,
            )
            return DeliveryAttempt(ok=False, retriable=True)

    def send(
        self,
        *,
        subject: str,
        body: str,
        from_addr: str,
        to_addrs: List[str],
        event: Dict[str, Any],
    ) -> bool:
        return deliver_with_retry(
            operation="Mailgun email",
            alert_id=event.get("alert_id"),
            attempt=lambda: self._send_once(
                subject=subject,
                body=body,
                from_addr=from_addr,
                to_addrs=to_addrs,
                event=event,
            ),
        )


def build_smtp_backend(alert: Dict[str, Any]) -> Optional[SmtpEmailBackend]:
    host = alert.get("smtp_host") or os.environ.get("SMTP_HOST")
    port_raw = alert.get("smtp_port") or os.environ.get("SMTP_PORT", "587")
    username = alert.get("smtp_user") or os.environ.get("SMTP_USER")
    password = alert.get("smtp_password") or os.environ.get("SMTP_PASSWORD")

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

    try:
        port = int(port_raw)
    except (TypeError, ValueError, OverflowError):
        logger.warning("Invalid SMTP port %r; expected an integer.", port_raw)
        return None
    if port < 1 or port > 65535:
        logger.warning("Invalid SMTP port %r; expected 1..65535.", port_raw)
        return None

    use_ssl = env_bool("SMTP_USE_SSL") or port == 465
    use_tls = not use_ssl and env_bool("SMTP_USE_TLS", default=port == 587)

    return SmtpEmailBackend(
        host=str(host).strip(),
        port=port,
        username=str(username).strip(),
        password=str(password),
        use_tls=use_tls,
        use_ssl=use_ssl,
    )


def build_sendgrid_backend() -> Optional[SendGridEmailBackend]:
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key or not str(api_key).strip():
        logger.warning(
            "SendGrid email requested but SENDGRID_API_KEY is missing."
        )
        return None
    return SendGridEmailBackend(api_key=str(api_key).strip())


def build_mailgun_backend() -> Optional[MailgunEmailBackend]:
    api_key = os.environ.get("MAILGUN_API_KEY")
    domain = os.environ.get("MAILGUN_DOMAIN")
    if not api_key or not str(api_key).strip():
        logger.warning(
            "Mailgun email requested but MAILGUN_API_KEY is missing."
        )
        return None
    if not domain or not str(domain).strip():
        logger.warning(
            "Mailgun email requested but MAILGUN_DOMAIN is missing."
        )
        return None
    api_base = os.environ.get("MAILGUN_API_BASE", "https://api.mailgun.net")
    return MailgunEmailBackend(
        api_key=str(api_key).strip(),
        domain=str(domain).strip(),
        api_base=str(api_base).strip(),
    )


def build_email_backend(alert: Dict[str, Any]) -> Optional[EmailDeliveryBackend]:
    provider = resolve_email_provider()
    if provider == "sendgrid":
        return build_sendgrid_backend()
    if provider == "mailgun":
        return build_mailgun_backend()
    return build_smtp_backend(alert)
