"""Hosted staging compose/image must wire live vs ready probes correctly.

#521 added Dockerfile.web HEALTHCHECK, compose api readiness, and a CI
workflow that waits on postgres+api then polls /health/worker. Two
regressions are cheap to reintroduce and expensive in staging:

- Image HEALTHCHECK probing /health/ready fails the web image in
  file-mode / no-DB contexts (ready 503s without PostgreSQL).
- Compose api healthcheck probing /health/live lets ``compose --wait``
  succeed before migrations, so acceptance hits a not-ready API.
- Publishing the API on 0.0.0.0 instead of loopback exposes staging
  without the TLS proxy documented in DEPLOYMENT.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_WEB = REPO_ROOT / "Dockerfile.web"
COMPOSE_STAGING = REPO_ROOT / "docker-compose.staging.yml"
STAGING_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "staging-readiness.yml"


def _service_block(compose: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n((?:    .*\n|\n)*)",
        compose,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"docker-compose.staging.yml has no {name} service")
    return match.group(0)


def test_dockerfile_web_healthcheck_probes_live_on_loopback() -> None:
    """Image HEALTHCHECK is process liveness — it must not require the DB."""
    dockerfile = DOCKERFILE_WEB.read_text(encoding="utf-8")
    healthchecks = re.findall(
        r"^HEALTHCHECK\b[^\n]*(?:\n[ \t]+[^\n]+)*",
        dockerfile,
        re.MULTILINE,
    )
    assert len(healthchecks) == 1, "Dockerfile.web must declare exactly one HEALTHCHECK"
    probe = healthchecks[0]
    assert "/health/live" in probe
    assert "/health/ready" not in probe
    assert "/health/worker" not in probe
    assert "127.0.0.1:8000" in probe


def test_compose_api_healthcheck_probes_ready_and_binds_loopback() -> None:
    """compose --wait must wait for DB readiness, not process liveness."""
    compose = COMPOSE_STAGING.read_text(encoding="utf-8")
    api = _service_block(compose, "api")

    assert '"127.0.0.1:${MARKET_HELM_PORT:-8000}:8000"' in api or (
        "127.0.0.1:${MARKET_HELM_PORT:-8000}:8000" in api
    )
    assert re.search(r"0\.0\.0\.0:.*8000", api) is None

    assert "/health/ready" in api
    assert "/health/live" not in api
    assert "postgres: {condition: service_healthy}" in api or (
        "condition: service_healthy" in api and "postgres:" in api
    )


def test_staging_readiness_waits_on_api_then_polls_worker_heartbeat() -> None:
    """Worker uses the API image; inherited HEALTHCHECK hits :8000 and is wrong.

    CI must --wait postgres+api only, start worker without --wait, then prove
    readiness via /health/worker rather than compose service_healthy.
    """
    workflow = STAGING_WORKFLOW.read_text(encoding="utf-8")

    compose_cmd = r"docker compose -f docker-compose\.staging\.yml"
    assert re.search(
        compose_cmd + r" up -d --build --wait postgres api",
        workflow,
    ), "compose --wait must name postgres and api only"
    assert re.search(compose_cmd + r" up -d worker", workflow)
    assert not re.search(
        compose_cmd + r" up -d(?: --build)? --wait(?: .*)? worker",
        workflow,
    )
    assert "/health/worker" in workflow
    assert "payload.get('ok') is True" in workflow
