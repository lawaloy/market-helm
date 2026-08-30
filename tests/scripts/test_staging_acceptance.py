"""Tests for the hosted staging acceptance harness."""

from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from scripts.staging_acceptance import (
    AcceptanceError,
    AcceptanceRunner,
    ApiClient,
    _bootstrap_loopback_credentials,
    build_report,
    normalize_base_url,
)


class _Response:
    def __init__(
        self,
        status: int,
        body: bytes,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
    ):
        self.status = status
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_normalize_base_url_requires_https_off_loopback() -> None:
    assert normalize_base_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    assert normalize_base_url("http://localhost:8000/api/") == "http://localhost:8000/api"
    assert normalize_base_url("https://staging.example.com/") == "https://staging.example.com"
    with pytest.raises(AcceptanceError, match="must use HTTPS"):
        normalize_base_url("http://staging.example.com")


@pytest.mark.parametrize(
    "url",
    [
        "staging.example.com",
        "ftp://staging.example.com",
        "https://user:secret@staging.example.com",
        "https://staging.example.com?token=secret",
        "https://staging.example.com/#token",
    ],
)
def test_normalize_base_url_rejects_unsafe_shapes(url: str) -> None:
    with pytest.raises(AcceptanceError):
        normalize_base_url(url)


def test_api_client_decodes_json_without_leaking_auth_into_url() -> None:
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        return _Response(200, b'{"status":"healthy"}')

    client = ApiClient("https://staging.example.com", timeout=3, opener=opener)
    payload = client.json("GET", "/health/live", token="private-token")

    assert payload == {"status": "healthy"}
    assert seen == {
        "url": "https://staging.example.com/health/live",
        "authorization": "Bearer private-token",
        "timeout": 3,
    }


def test_api_client_rejects_nonpositive_timeout() -> None:
    with pytest.raises(AcceptanceError, match="greater than zero"):
        ApiClient("https://staging.example.com", timeout=0)


def test_disposable_tenant_bootstrap_is_loopback_only() -> None:
    class Client:
        base_url = "http://127.0.0.1:8012"

        def __init__(self):
            self.payloads = []

        def json(self, method, path, *, payload):
            assert (method, path) == ("POST", "/api/auth/register")
            self.payloads.append(payload)
            return {"access_token": "unused"}

    client = Client()
    credentials = _bootstrap_loopback_credentials(client)
    assert len(credentials) == 2
    assert credentials[0][0] != credentials[1][0]
    assert all("@example.test" in email for email, _ in credentials)
    assert client.payloads == [
        {"email": email, "password": password} for email, password in credentials
    ]

    client.base_url = "https://staging.example.com"
    with pytest.raises(AcceptanceError, match="restricted to loopback"):
        _bootstrap_loopback_credentials(client)


class _OperationalClient:
    base_url = "https://staging.example.com"

    def json(self, method, path, **kwargs):
        assert method == "GET"
        responses = {
            "/health/live": {"status": "healthy", "service": "api"},
            "/health/ready": {
                "status": "ready",
                "database": {"ok": True, "schema_version": 5, "expected_schema_version": 5},
            },
            "/health/worker": {"status": "healthy", "ok": True, "worker_id": "worker-1"},
            "/api/alerts/config": {"detail": "Authentication required."},
        }
        if path == "/api/alerts/config":
            assert kwargs["expected_status"] == 401
        return responses[path]

    def request(self, method, path, **_kwargs):
        assert (method, path) == ("GET", "/metrics")
        return (
            200,
            b"# TYPE markethelm_http_requests_total counter\nmarkethelm_http_requests_total 1\n",
            {"Content-Type": "text/plain; version=0.0.4"},
        )


def test_operational_checks_cover_hosted_dependencies() -> None:
    runner = AcceptanceRunner(_OperationalClient())
    runner.run_operational_checks()

    assert [result.name for result in runner.results] == [
        "API liveness",
        "Database readiness",
        "Worker heartbeat",
        "Prometheus metrics",
        "Hosted authentication boundary",
    ]
    assert all(result.status == "passed" for result in runner.results)


def test_ingress_check_requires_exact_cors_and_request_id() -> None:
    class Client(_OperationalClient):
        def request(self, method, path, **kwargs):
            if path == "/metrics":
                return super().request(method, path, **kwargs)
            origin = kwargs["headers"]["Origin"]
            headers = {"X-Request-ID": "request-1"}
            if origin == "https://staging.example.com":
                headers.update({
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Strict-Transport-Security": "max-age=31536000",
                })
            return 200, b'{"status":"healthy"}', headers

    runner = AcceptanceRunner(Client())
    runner.run_operational_checks(ingress_origin="https://staging.example.com")
    assert runner.results[-1].name == "Ingress and CORS"
    assert runner.results[-1].status == "passed"


def test_ingress_check_fails_without_hsts_on_https() -> None:
    class Client(_OperationalClient):
        def request(self, method, path, **kwargs):
            if path == "/metrics":
                return super().request(method, path, **kwargs)
            origin = kwargs["headers"]["Origin"]
            return 200, b"{}", {
                "X-Request-ID": "request-1",
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            }

    runner = AcceptanceRunner(Client())
    runner.run_operational_checks(ingress_origin="https://staging.example.com")
    assert runner.results[-1].status == "failed"
    assert "Strict-Transport-Security" in runner.results[-1].detail


def test_ingress_check_rejects_origin_with_path() -> None:
    runner = AcceptanceRunner(_OperationalClient())
    runner.run_operational_checks(ingress_origin="https://staging.example.com/app")
    assert runner.results[-1].status == "failed"
    assert "must not contain a path" in runner.results[-1].detail


def test_readiness_rejects_file_mode_even_when_endpoint_says_ready() -> None:
    client = _OperationalClient()

    def file_mode_json(method, path, **kwargs):
        if path == "/health/ready":
            return {"status": "ready", "database": "disabled"}
        return _OperationalClient.json(client, method, path, **kwargs)

    client.json = file_mode_json
    runner = AcceptanceRunner(client)
    runner.run_operational_checks(skip_worker=True)

    readiness = next(result for result in runner.results if result.name == "Database readiness")
    assert readiness.status == "failed"
    assert "enabled hosted database" in readiness.detail


class _TenantClient:
    base_url = "https://staging.example.com"

    def __init__(self, *, nonempty: bool = False) -> None:
        self.tokens = {"a@example.com": "token-a", "b@example.com": "token-b"}
        initial_alerts = [{"id": "real-watch"}] if nonempty else []
        self.configs = {
            "token-a": {"defaults": {}, "alerts": list(initial_alerts)},
            "token-b": {"defaults": {}, "alerts": []},
        }
        self.put_payloads: list[tuple[str, dict[str, Any]]] = []

    def json(self, method, path, *, token=None, payload=None, **_kwargs):
        if (method, path) == ("POST", "/api/auth/login"):
            return {"access_token": self.tokens[payload["email"]]}
        if (method, path) == ("GET", "/api/auth/me"):
            email = next(email for email, saved_token in self.tokens.items() if saved_token == token)
            return {"email": email}
        if (method, path) == ("GET", "/api/alerts/config"):
            return {
                "exists": True,
                "config": json.loads(json.dumps(self.configs[token])),
                "channels": {"email_smtp": True, "email_recipients": False, "webhook_url": False},
            }
        if (method, path) == ("PUT", "/api/alerts/config"):
            self.configs[token] = json.loads(json.dumps(payload))
            self.put_payloads.append((token, json.loads(json.dumps(payload))))
            return {"exists": True, "config": payload}
        if (method, path) == ("GET", "/api/alerts/status"):
            active = sum(bool(alert.get("enabled")) for alert in self.configs[token]["alerts"])
            return {"active_watches": active}
        if (method, path) == ("POST", "/api/alerts/test"):
            ids = {alert["id"] for alert in self.configs[token]["alerts"]}
            assert payload["id"] in ids
            assert payload["dry_run"] is True
            return {
                "alert_id": payload["id"],
                "status": "dry_run",
                "notifiers": [],
                "previews": [{"notifier": "LogNotifier", "payload": {}}],
            }
        raise AssertionError((method, path, token, payload))


def test_tenant_check_proves_isolation_and_restores_empty_configs() -> None:
    client = _TenantClient()
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "passed"
    assert client.configs == {
        "token-a": {"defaults": {}, "alerts": []},
        "token-b": {"defaults": {}, "alerts": []},
    }
    written_ids = [
        payload["alerts"][0]["id"]
        for _, payload in client.put_payloads
        if payload["alerts"]
    ]
    assert len(written_ids) == 2
    assert written_ids[0] != written_ids[1]
    assert all(
        alert["notifications"] == ["log"]
        for _, payload in client.put_payloads
        for alert in payload["alerts"]
    )


def test_tenant_check_refuses_nonempty_account_without_overwriting_it() -> None:
    client = _TenantClient(nonempty=True)
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "dedicated staging accounts" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["alerts"] == [{"id": "real-watch"}]


def test_report_contains_results_but_no_credentials() -> None:
    runner = AcceptanceRunner(_OperationalClient())
    runner.run_operational_checks(skip_worker=True)

    report = build_report("https://staging.example.com", runner.results)
    serialized = json.dumps(report)

    assert report["status"] == "incomplete"
    assert report["schema_version"] == 1
    assert any(check["status"] == "skipped" for check in report["checks"])
    assert "password" not in serialized.lower()
    assert "token" not in serialized.lower()


def test_staging_compose_worker_healthcheck_supports_wait() -> None:
    """compose up --wait fails when the worker healthcheck is disabled."""
    compose = Path(__file__).resolve().parents[2] / "docker-compose.staging.yml"
    text = compose.read_text(encoding="utf-8")
    worker = text.split("  worker:\n", 1)[1].split("volumes:\n", 1)[0]
    assert "disable: true" not in worker
    assert "healthcheck:" in worker
    assert "/proc/1/cmdline" in worker
