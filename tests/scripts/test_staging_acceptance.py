"""Tests for the hosted staging acceptance harness."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from scripts.staging_acceptance import (
    AcceptanceError,
    AcceptanceRunner,
    ApiClient,
    CheckResult,
    _NoRedirectHandler,
    _bootstrap_loopback_credentials,
    _credentials_from_env,
    build_report,
    main,
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
    assert normalize_base_url("http://[::1]:8000/") == "http://[::1]:8000"
    assert normalize_base_url("https://staging.example.com/") == "https://staging.example.com"
    with pytest.raises(AcceptanceError, match="must use HTTPS"):
        normalize_base_url("http://staging.example.com")


def test_redirect_handler_does_not_follow() -> None:
    request = urllib.request.Request(
        "https://staging.example.com/health/live",
        headers={"Authorization": "Bearer secret-token"},
    )
    followed = _NoRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, "https://evil.example/steal"
    )
    assert followed is None


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


def _http_error(url: str, status: int, body: bytes) -> urllib.error.HTTPError:
    headers = Message()
    headers["Content-Type"] = "application/json"
    return urllib.error.HTTPError(url, status, "error", headers, io.BytesIO(body))


def test_api_client_accepts_http_error_when_status_is_expected() -> None:
    def opener(request, *, timeout):
        raise _http_error(
            request.full_url, 401, b'{"detail":"Authentication required."}'
        )

    client = ApiClient("https://staging.example.com", opener=opener)
    payload = client.json("GET", "/api/alerts/config", expected_status=401)
    assert payload == {"detail": "Authentication required."}


def test_api_client_http_error_includes_json_detail() -> None:
    def opener(request, *, timeout):
        raise _http_error(request.full_url, 503, b'{"detail":"worker unavailable"}')

    client = ApiClient("https://staging.example.com", opener=opener)
    with pytest.raises(AcceptanceError, match="worker unavailable"):
        client.json("GET", "/health/worker")


def test_api_client_rejects_non_object_json() -> None:
    def opener(request, *, timeout):
        return _Response(200, b'["healthy"]')

    client = ApiClient("https://staging.example.com", opener=opener)
    with pytest.raises(AcceptanceError, match="non-object"):
        client.json("GET", "/health/live")


def test_api_client_connection_failure_is_acceptance_error() -> None:
    def opener(request, *, timeout):
        raise urllib.error.URLError("timed out")

    client = ApiClient("https://staging.example.com", opener=opener)
    with pytest.raises(AcceptanceError, match="could not connect"):
        client.request("GET", "/health/live")


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


class _IngressClient(_OperationalClient):
    def __init__(
        self,
        *,
        allow_untrusted: bool = False,
        request_id: str = "request-1",
        include_hsts: bool = True,
        base_url: str = "https://staging.example.com",
    ) -> None:
        self.allow_untrusted = allow_untrusted
        self.request_id = request_id
        self.include_hsts = include_hsts
        self.base_url = base_url

    def request(self, method, path, **kwargs):
        if path == "/metrics":
            return super().request(method, path, **kwargs)
        origin = kwargs["headers"]["Origin"]
        headers = {"X-Request-ID": self.request_id}
        trusted = origin == self.base_url or (
            self.allow_untrusted and origin == "https://untrusted.invalid"
        )
        if trusted:
            headers.update({
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            })
            if self.include_hsts:
                headers["Strict-Transport-Security"] = "max-age=31536000"
        return 200, b'{"status":"healthy"}', headers


def test_ingress_check_fails_when_untrusted_origin_is_allowed() -> None:
    runner = AcceptanceRunner(_IngressClient(allow_untrusted=True))
    runner.run_operational_checks(ingress_origin="https://staging.example.com")
    assert runner.results[-1].status == "failed"
    assert "untrusted" in runner.results[-1].detail


@pytest.mark.parametrize("request_id", ["", "x" * 129])
def test_ingress_check_requires_valid_request_id(request_id: str) -> None:
    runner = AcceptanceRunner(_IngressClient(request_id=request_id))
    runner.run_operational_checks(ingress_origin="https://staging.example.com")
    assert runner.results[-1].status == "failed"
    assert "X-Request-ID" in runner.results[-1].detail


def test_ingress_check_skips_hsts_on_loopback_http() -> None:
    runner = AcceptanceRunner(
        _IngressClient(include_hsts=False, base_url="http://127.0.0.1:8012")
    )
    runner.run_operational_checks(ingress_origin="http://127.0.0.1:8012")
    assert runner.results[-1].name == "Ingress and CORS"
    assert runner.results[-1].status == "passed"


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


def test_readiness_rejects_schema_mismatch() -> None:
    client = _OperationalClient()

    def mismatched_json(method, path, **kwargs):
        if path == "/health/ready":
            return {
                "status": "ready",
                "database": {
                    "ok": True,
                    "schema_version": 4,
                    "expected_schema_version": 5,
                },
            }
        return _OperationalClient.json(client, method, path, **kwargs)

    client.json = mismatched_json
    runner = AcceptanceRunner(client)
    runner.run_operational_checks(skip_worker=True)

    readiness = next(result for result in runner.results if result.name == "Database readiness")
    assert readiness.status == "failed"
    assert "schema is 4, expected 5" in readiness.detail


def test_metrics_require_markethelm_counters() -> None:
    class Client(_OperationalClient):
        def request(self, method, path, **_kwargs):
            assert (method, path) == ("GET", "/metrics")
            return 200, b"# TYPE http_requests_total counter\n", {"Content-Type": "text/plain"}

    runner = AcceptanceRunner(Client())
    runner.run_operational_checks(skip_worker=True)
    metrics = next(result for result in runner.results if result.name == "Prometheus metrics")
    assert metrics.status == "failed"
    assert "HTTP counters" in metrics.detail


class _TenantClient:
    base_url = "https://staging.example.com"

    def __init__(
        self,
        *,
        nonempty: bool = False,
        defaults: dict[str, Any] | None = None,
        webhook_url: bool = False,
        email_recipients: bool = False,
        fail_restore: bool = False,
    ) -> None:
        self.tokens = {"a@example.com": "token-a", "b@example.com": "token-b"}
        initial_alerts = [{"id": "real-watch"}] if nonempty else []
        self.configs = {
            "token-a": {"defaults": dict(defaults or {}), "alerts": list(initial_alerts)},
            "token-b": {"defaults": {}, "alerts": []},
        }
        self.channels = {
            "email_smtp": True,
            "email_recipients": email_recipients,
            "webhook_url": webhook_url,
        }
        self.fail_restore = fail_restore
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
                "channels": dict(self.channels),
            }
        if (method, path) == ("PUT", "/api/alerts/config"):
            if self.fail_restore and not (payload or {}).get("alerts"):
                raise RuntimeError("restore exploded")
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


def test_tenant_check_refuses_accounts_with_notification_secrets() -> None:
    client = _TenantClient(webhook_url=True)
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "notification secrets" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["alerts"] == []


def test_tenant_check_refuses_account_with_defaults_mailbox_without_overwriting_it() -> None:
    """Onboarding tenants often have defaults.email_to and no watches yet."""
    client = _TenantClient(defaults={"email_to": "ops@example.com"})
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "dedicated staging accounts" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["defaults"]["email_to"] == "ops@example.com"
    assert client.configs["token-a"]["alerts"] == []


def test_tenant_check_refuses_accounts_with_email_recipient_secrets() -> None:
    """email_recipients must refuse even when public defaults/alerts look empty."""
    client = _TenantClient(email_recipients=True)
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "notification secrets" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["alerts"] == []


def test_tenant_check_fails_when_configs_leak_across_accounts() -> None:
    class LeakyClient(_TenantClient):
        def json(self, method, path, *, token=None, payload=None, **kwargs):
            if (method, path) == ("PUT", "/api/alerts/config"):
                alert = json.loads(json.dumps(payload["alerts"][0]))
                for config in self.configs.values():
                    existing = {item.get("id") for item in config["alerts"]}
                    if alert["id"] not in existing:
                        config["alerts"].append(alert)
                self.put_payloads.append((token, json.loads(json.dumps(payload))))
                return {"exists": True, "config": payload}
            return super().json(method, path, token=token, payload=payload, **kwargs)

    client = LeakyClient()
    runner = AcceptanceRunner(client)
    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    isolation = next(result for result in runner.results if result.name == "Tenant isolation")
    assert isolation.status == "failed"
    assert "account boundary" in isolation.detail


def test_tenant_check_rejects_same_email_accounts() -> None:
    client = _TenantClient()
    client.tokens = {"a@example.com": "token-a", "A@example.com": "token-b"}
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("A@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "different email" in runner.results[-1].detail
    assert client.put_payloads == []


def test_tenant_check_refuses_login_without_access_token() -> None:
    """A login payload without a bearer must not proceed to GET/PUT config."""

    class NoTokenClient(_TenantClient):
        def json(self, method, path, *, token=None, payload=None, **kwargs):
            if (method, path) == ("POST", "/api/auth/login"):
                return {}
            return super().json(method, path, token=token, payload=payload, **kwargs)

    client = NoTokenClient()
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "no access token" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["alerts"] == []


def test_tenant_check_refuses_when_authenticated_identity_does_not_match() -> None:
    """Login returning another account's token must not write this tenant's config."""

    class MismatchClient(_TenantClient):
        def json(self, method, path, *, token=None, payload=None, **kwargs):
            if (method, path) == ("GET", "/api/auth/me"):
                return {"email": "other@example.com"}
            return super().json(method, path, token=token, payload=payload, **kwargs)

    client = MismatchClient()
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "authenticated identity did not match" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["alerts"] == []
    assert client.configs["token-b"]["alerts"] == []


@pytest.mark.parametrize(
    "broken",
    [
        {"exists": True, "config": [], "channels": {"webhook_url": False}},
        {"exists": True, "config": {"defaults": {}, "alerts": []}},
    ],
)
def test_tenant_check_refuses_unexpected_config_shape_without_overwriting(
    broken: dict[str, Any],
) -> None:
    """Garbage GET /config must fail closed before the harness writes watches."""

    class ShapelessClient(_TenantClient):
        def json(self, method, path, *, token=None, payload=None, **kwargs):
            if (method, path) == ("GET", "/api/alerts/config"):
                return json.loads(json.dumps(broken))
            return super().json(method, path, token=token, payload=payload, **kwargs)

    client = ShapelessClient()
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    assert runner.results[-1].status == "failed"
    assert "unexpected shape" in runner.results[-1].detail
    assert client.put_payloads == []
    assert client.configs["token-a"]["alerts"] == []


def test_tenant_check_fails_when_watch_index_is_not_isolated() -> None:
    """Config ids can look isolated while GET /status still shares the index."""

    class SharedIndexClient(_TenantClient):
        def json(self, method, path, *, token=None, payload=None, **kwargs):
            if (method, path) == ("GET", "/api/alerts/status"):
                return {"active_watches": 2}
            return super().json(method, path, token=token, payload=payload, **kwargs)

    client = SharedIndexClient()
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    isolation = next(result for result in runner.results if result.name == "Tenant isolation")
    assert isolation.status == "failed"
    assert "watch index is not isolated" in isolation.detail
    assert client.configs == {
        "token-a": {"defaults": {}, "alerts": []},
        "token-b": {"defaults": {}, "alerts": []},
    }


@pytest.mark.parametrize(
    "override",
    [
        {"alert_id": "other-tenant"},
        {"status": "sent"},
        {"previews": [{"notifier": "EmailNotifier", "payload": {}}]},
    ],
)
def test_tenant_check_fails_when_log_only_dry_run_is_not_isolated(
    override: dict[str, Any],
) -> None:
    """Config ids can look isolated while /test dry-runs the sibling or a live send."""

    class DryRunClient(_TenantClient):
        def json(self, method, path, *, token=None, payload=None, **kwargs):
            if (method, path) == ("POST", "/api/alerts/test"):
                body = super().json(method, path, token=token, payload=payload, **kwargs)
                body.update(override)
                return body
            return super().json(method, path, token=token, payload=payload, **kwargs)

    client = DryRunClient()
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    isolation = next(result for result in runner.results if result.name == "Tenant isolation")
    assert isolation.status == "failed"
    assert "log-only dry run failed" in isolation.detail
    assert client.configs == {
        "token-a": {"defaults": {}, "alerts": []},
        "token-b": {"defaults": {}, "alerts": []},
    }


def test_tenant_cleanup_failure_is_recorded() -> None:
    client = _TenantClient(fail_restore=True)
    runner = AcceptanceRunner(client)

    runner.run_tenant_isolation(
        [("a@example.com", "password-a"), ("b@example.com", "password-b")]
    )

    isolation = next(result for result in runner.results if result.name == "Tenant isolation")
    cleanups = [result for result in runner.results if result.name == "Tenant cleanup"]
    assert isolation.status == "passed"
    assert cleanups
    assert all(result.status == "failed" for result in cleanups)
    assert any("could not restore dedicated tenant" in result.detail for result in cleanups)
    assert all(config["alerts"] for config in client.configs.values())


def test_credentials_from_env_requires_both_tenants(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_A_EMAIL", "a@example.com")
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_A_PASSWORD", "pw-a")
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_B_EMAIL", "b@example.com")
    monkeypatch.delenv("MARKET_HELM_STAGING_TENANT_B_PASSWORD", raising=False)
    with pytest.raises(AcceptanceError, match="TENANT"):
        _credentials_from_env()


def test_credentials_from_env_reads_stripped_emails(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_A_EMAIL", " a@example.com ")
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_A_PASSWORD", "pw-a")
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_B_EMAIL", "b@example.com")
    monkeypatch.setenv("MARKET_HELM_STAGING_TENANT_B_PASSWORD", "pw-b")
    assert _credentials_from_env() == [
        ("a@example.com", "pw-a"),
        ("b@example.com", "pw-b"),
    ]


def test_main_invalid_base_url_exits_two(capsys) -> None:
    assert main(["--base-url", "http://staging.example.com"]) == 2
    assert "HTTPS" in capsys.readouterr().err


def test_main_bootstrap_without_tenant_check_fails(monkeypatch, capsys) -> None:
    class FakeClient:
        def __init__(self, base_url, *, timeout=10.0, opener=None):
            self.base_url = normalize_base_url(base_url)

    class FakeRunner:
        def __init__(self, client):
            self.results: list[CheckResult] = []

        def run_operational_checks(self, **_kwargs) -> None:
            return None

    monkeypatch.setattr("scripts.staging_acceptance.ApiClient", FakeClient)
    monkeypatch.setattr("scripts.staging_acceptance.AcceptanceRunner", FakeRunner)
    assert main(["--base-url", "http://127.0.0.1:8000", "--bootstrap-loopback-tenants"]) == 1
    captured = capsys.readouterr()
    assert "--tenant-check" in captured.out


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
