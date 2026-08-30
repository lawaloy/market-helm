#!/usr/bin/env python3
"""Verify a hosted MarketHelm staging deployment through its public API.

The default checks are read-only.  The optional tenant-isolation check requires
two dedicated, verified accounts with empty alert configurations.  It refuses to
touch non-empty configurations, creates only log-channel watches, and restores
both accounts to an empty configuration before exiting.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit


class AcceptanceError(RuntimeError):
    """A staging acceptance assertion failed."""


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    duration_ms: int


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Fail redirects so credentials and bearer tokens stay on the chosen host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_base_url(raw: str) -> str:
    """Return a safe API base URL; plain HTTP is limited to loopback hosts."""
    value = raw.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AcceptanceError("Base URL must be an absolute http(s) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AcceptanceError("Base URL must not include credentials, query, or fragment.")
    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise AcceptanceError("Non-loopback staging URLs must use HTTPS.")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        if timeout <= 0:
            raise AcceptanceError("Request timeout must be greater than zero.")
        self.timeout = timeout
        self._opener = opener or urllib.request.build_opener(_NoRedirectHandler()).open

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> tuple[int, bytes, dict[str, str]]:
        request_headers = {
            "Accept": "application/json",
            "User-Agent": "markethelm-staging-acceptance/1",
        }
        request_headers.update(headers or {})
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        data = None
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = response.status
                body = response.read()
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read()
            response_headers = dict(exc.headers.items())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AcceptanceError(f"{method} {path} could not connect: {exc}") from exc
        if status != expected_status:
            detail = _response_detail(body)
            raise AcceptanceError(
                f"{method} {path} returned HTTP {status}, expected {expected_status}: {detail}"
            )
        return status, body, response_headers

    def json(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        _, body, _ = self.request(
            method,
            path,
            token=token,
            payload=payload,
            expected_status=expected_status,
        )
        try:
            decoded = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceError(f"{method} {path} did not return valid JSON.") from exc
        if not isinstance(decoded, dict):
            raise AcceptanceError(f"{method} {path} returned a non-object JSON response.")
        return decoded


def _response_detail(body: bytes) -> str:
    try:
        decoded = json.loads(body)
        if isinstance(decoded, dict) and decoded.get("detail"):
            return str(decoded["detail"])[:300]
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return body.decode("utf-8", errors="replace")[:300] or "empty response"


class AcceptanceRunner:
    def __init__(self, client: ApiClient) -> None:
        self.client = client
        self.results: list[CheckResult] = []

    def check(self, name: str, action: Callable[[], str]) -> bool:
        started = time.monotonic()
        try:
            detail = action()
            status = "passed"
        except Exception as exc:
            detail = str(exc)
            status = "failed"
        duration_ms = round((time.monotonic() - started) * 1000)
        self.results.append(CheckResult(name, status, detail, duration_ms))
        marker = "PASS" if status == "passed" else "FAIL"
        print(f"[{marker}] {name}: {detail}")
        return status == "passed"

    def skip(self, name: str, detail: str) -> None:
        self.results.append(CheckResult(name, "skipped", detail, 0))
        print(f"[SKIP] {name}: {detail}")

    def run_operational_checks(
        self,
        *,
        skip_worker: bool = False,
        ingress_origin: str | None = None,
    ) -> None:
        self.check("API liveness", self._check_live)
        self.check("Database readiness", self._check_ready)
        if skip_worker:
            self.skip("Worker heartbeat", "skipped by operator; report cannot be signed off")
        else:
            self.check("Worker heartbeat", self._check_worker)
        self.check("Prometheus metrics", self._check_metrics)
        self.check("Hosted authentication boundary", self._check_auth_boundary)
        if ingress_origin:
            self.check("Ingress and CORS", lambda: self._check_ingress(ingress_origin))

    def _check_live(self) -> str:
        payload = self.client.json("GET", "/health/live")
        if payload.get("status") != "healthy" or payload.get("service") != "api":
            raise AcceptanceError(f"unexpected liveness payload: {payload}")
        return "API reports healthy"

    def _check_ready(self) -> str:
        payload = self.client.json("GET", "/health/ready")
        database = payload.get("database")
        if payload.get("status") != "ready" or not isinstance(database, dict):
            raise AcceptanceError("readiness does not report an enabled hosted database")
        if database.get("ok") is not True:
            raise AcceptanceError(f"database is not healthy: {database}")
        version = database.get("schema_version")
        expected = database.get("expected_schema_version")
        if version != expected:
            raise AcceptanceError(f"schema is {version}, expected {expected}")
        return f"database healthy at schema {version}"

    def _check_worker(self) -> str:
        payload = self.client.json("GET", "/health/worker")
        if payload.get("status") != "healthy" or payload.get("ok") is not True:
            raise AcceptanceError(f"worker is not healthy: {payload}")
        return f"worker {payload.get('worker_id', 'unknown')} has a fresh heartbeat"

    def _check_metrics(self) -> str:
        _, body, headers = self.client.request("GET", "/metrics")
        text = body.decode("utf-8", errors="replace")
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        if "text/plain" not in content_type or "markethelm_http_requests_total" not in text:
            raise AcceptanceError("metrics response is missing MarketHelm HTTP counters")
        return "Prometheus counters are exposed"

    def _check_auth_boundary(self) -> str:
        payload = self.client.json(
            "GET", "/api/alerts/config", expected_status=401
        )
        if not payload.get("detail"):
            raise AcceptanceError("anonymous alert config request did not return an auth error")
        return "anonymous tenant data access is rejected"

    def _check_ingress(self, expected_origin: str) -> str:
        parsed_origin = urlsplit(expected_origin.strip())
        if parsed_origin.path not in {"", "/"}:
            raise AcceptanceError("CORS origin must not contain a path")
        origin = normalize_base_url(expected_origin)
        _, _, headers = self.client.request(
            "GET", "/health/live", headers={"Origin": origin}
        )
        lowered = {key.lower(): value for key, value in headers.items()}
        request_id = lowered.get("x-request-id", "")
        if not request_id or len(request_id) > 128:
            raise AcceptanceError("ingress response has no valid X-Request-ID")
        if lowered.get("access-control-allow-origin") != origin:
            raise AcceptanceError("CORS does not allow the expected public origin")
        if lowered.get("access-control-allow-credentials", "").lower() != "true":
            raise AcceptanceError("CORS credential support is not enabled")
        if self.client.base_url.startswith("https://"):
            hsts = lowered.get("strict-transport-security", "").lower()
            if "max-age=" not in hsts:
                raise AcceptanceError("HTTPS ingress is missing Strict-Transport-Security")

        _, _, rejected_headers = self.client.request(
            "GET", "/health/live", headers={"Origin": "https://untrusted.invalid"}
        )
        rejected = {key.lower(): value for key, value in rejected_headers.items()}
        if rejected.get("access-control-allow-origin"):
            raise AcceptanceError("CORS unexpectedly allows an untrusted origin")
        return "request IDs and exact-origin CORS are enforced; TLS policy is valid when applicable"

    def run_tenant_isolation(self, credentials: list[tuple[str, str]]) -> None:
        if len(credentials) != 2:
            raise AcceptanceError("Exactly two tenant credential pairs are required.")
        tokens: list[str] = []
        configs: list[dict[str, Any]] = []
        emails: list[str] = []

        def action() -> str:
            for email, password in credentials:
                login = self.client.json(
                    "POST", "/api/auth/login", payload={"email": email, "password": password}
                )
                token = login.get("access_token")
                if not isinstance(token, str) or not token:
                    raise AcceptanceError(f"login for {email} returned no access token")
                me = self.client.json("GET", "/api/auth/me", token=token)
                if str(me.get("email", "")).lower() != email.lower():
                    raise AcceptanceError(f"authenticated identity did not match {email}")
                tokens.append(token)
                emails.append(email)

            if emails[0].lower() == emails[1].lower():
                raise AcceptanceError("tenant accounts must have different email addresses")

            for token in tokens:
                response = self.client.json("GET", "/api/alerts/config", token=token)
                _assert_empty_dedicated_config(response)
                configs.append(response["config"])

            run_id = str(int(time.time() * 1000))
            ids = [f"staging_a_{run_id}", f"staging_b_{run_id}"]
            symbols = ["AAPL", "MSFT"]
            for index, token in enumerate(tokens):
                config = {
                    "defaults": {},
                    "alerts": [{
                        "id": ids[index],
                        "name": f"Staging tenant {index + 1}",
                        "enabled": True,
                        "cooldown_minutes": 60,
                        "condition": {
                            "type": "price_threshold",
                            "symbol": symbols[index],
                            "operator": "greater_than",
                            "value": 999999,
                        },
                        "notifications": ["log"],
                    }],
                }
                self.client.json("PUT", "/api/alerts/config", token=token, payload=config)

            for index, token in enumerate(tokens):
                saved = self.client.json("GET", "/api/alerts/config", token=token)
                saved_ids = {
                    alert.get("id")
                    for alert in saved.get("config", {}).get("alerts", [])
                    if isinstance(alert, dict)
                }
                if ids[index] not in saved_ids or ids[1 - index] in saved_ids:
                    raise AcceptanceError(f"tenant {index + 1} alert config crossed account boundary")
                status = self.client.json("GET", "/api/alerts/status", token=token)
                if status.get("active_watches") != 1:
                    raise AcceptanceError(f"tenant {index + 1} watch index is not isolated")
                dry_run = self.client.json(
                    "POST",
                    "/api/alerts/test",
                    token=token,
                    payload={"id": ids[index], "dry_run": True},
                )
                previews = dry_run.get("previews") or []
                preview_notifiers = {
                    preview.get("notifier")
                    for preview in previews
                    if isinstance(preview, dict)
                }
                if (
                    dry_run.get("alert_id") != ids[index]
                    or dry_run.get("status") != "dry_run"
                    or "LogNotifier" not in preview_notifiers
                ):
                    raise AcceptanceError(f"tenant {index + 1} log-only dry run failed")
            return "two dedicated accounts retained isolated configs, indexes, and dry runs"

        try:
            self.check("Tenant isolation", action)
        finally:
            for index, token in enumerate(tokens):
                if index >= len(configs):
                    continue
                try:
                    self.client.json(
                        "PUT", "/api/alerts/config", token=token, payload=configs[index]
                    )
                except Exception as exc:
                    self.results.append(
                        CheckResult(
                            "Tenant cleanup",
                            "failed",
                            f"could not restore dedicated tenant {index + 1}: {exc}",
                            0,
                        )
                    )
                    print(f"[FAIL] Tenant cleanup: {exc}")


def _assert_empty_dedicated_config(response: dict[str, Any]) -> None:
    config = response.get("config")
    channels = response.get("channels")
    if not isinstance(config, dict) or not isinstance(channels, dict):
        raise AcceptanceError("tenant alert config response has an unexpected shape")
    defaults = config.get("defaults") or {}
    populated_defaults = {key: value for key, value in defaults.items() if value not in (None, "", False)}
    if config.get("alerts") or populated_defaults:
        raise AcceptanceError("tenant account is not empty; use dedicated staging accounts")
    if channels.get("webhook_url") or channels.get("email_recipients"):
        raise AcceptanceError("tenant account has notification secrets; refusing to overwrite it")


def _credentials_from_env() -> list[tuple[str, str]]:
    names = (
        ("MARKET_HELM_STAGING_TENANT_A_EMAIL", "MARKET_HELM_STAGING_TENANT_A_PASSWORD"),
        ("MARKET_HELM_STAGING_TENANT_B_EMAIL", "MARKET_HELM_STAGING_TENANT_B_PASSWORD"),
    )
    credentials = [(os.environ.get(email, "").strip(), os.environ.get(password, "")) for email, password in names]
    if any(not email or not password for email, password in credentials):
        raise AcceptanceError(
            "Tenant checks require MARKET_HELM_STAGING_TENANT_{A,B}_{EMAIL,PASSWORD}."
        )
    return credentials


def _bootstrap_loopback_credentials(client: ApiClient) -> list[tuple[str, str]]:
    hostname = urlsplit(client.base_url).hostname or ""
    if not _is_loopback(hostname):
        raise AcceptanceError("Disposable tenant bootstrap is restricted to loopback staging.")
    run_id = secrets.token_hex(8)
    password = f"Local-acceptance-{secrets.token_urlsafe(24)}"
    credentials = [
        (f"acceptance-a-{run_id}@example.test", password),
        (f"acceptance-b-{run_id}@example.test", password),
    ]
    for email, tenant_password in credentials:
        client.json(
            "POST",
            "/api/auth/register",
            payload={"email": email, "password": tenant_password},
        )
    return credentials


def build_report(base_url: str, results: list[CheckResult]) -> dict[str, Any]:
    statuses = {result.status for result in results}
    status = "passed"
    if "failed" in statuses:
        status = "failed"
    elif "skipped" in statuses:
        status = "incomplete"
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "status": status,
        "checks": [asdict(result) for result in results],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MARKET_HELM_STAGING_URL", "http://127.0.0.1:8000"),
        help="Staging API URL (or MARKET_HELM_STAGING_URL). Non-loopback URLs require HTTPS.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds.")
    parser.add_argument("--skip-worker", action="store_true", help="Skip the worker heartbeat check.")
    parser.add_argument(
        "--tenant-check",
        action="store_true",
        help="Run the guarded write-isolation check with dedicated accounts from environment variables.",
    )
    parser.add_argument(
        "--bootstrap-loopback-tenants",
        action="store_true",
        help="Create disposable tenant accounts; accepted only for a loopback base URL.",
    )
    parser.add_argument(
        "--ingress-origin",
        help="Validate request IDs, exact-origin CORS, and HSTS for HTTPS deployments.",
    )
    parser.add_argument("--report", type=Path, help="Optional path for a credential-free JSON report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        client = ApiClient(args.base_url, timeout=args.timeout)
    except AcceptanceError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    runner = AcceptanceRunner(client)
    runner.run_operational_checks(
        skip_worker=args.skip_worker,
        ingress_origin=args.ingress_origin,
    )
    if args.tenant_check:
        try:
            credentials = (
                _bootstrap_loopback_credentials(client)
                if args.bootstrap_loopback_tenants
                else _credentials_from_env()
            )
        except AcceptanceError as exc:
            runner.results.append(CheckResult("Tenant isolation", "failed", str(exc), 0))
            print(f"[FAIL] Tenant isolation: {exc}")
        else:
            runner.run_tenant_isolation(credentials)
    elif args.bootstrap_loopback_tenants:
        runner.results.append(
            CheckResult(
                "Tenant isolation",
                "failed",
                "--bootstrap-loopback-tenants requires --tenant-check",
                0,
            )
        )
        print("[FAIL] Tenant isolation: --bootstrap-loopback-tenants requires --tenant-check")

    report = build_report(client.base_url, runner.results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {args.report}")
    print(f"Overall: {report['status'].upper()}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
