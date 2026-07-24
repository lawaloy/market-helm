"""Tests for SPA deep-link fallback middleware."""

from pathlib import Path
from unittest.mock import patch

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from dashboard.backend.main import SpaFallbackMiddleware


async def _not_found(request):
    return PlainTextResponse("missing", status_code=404)


def _make_app() -> Starlette:
    return Starlette(
        routes=[Route("/{full_path:path}", _not_found, methods=["GET", "POST"])]
    )


def test_spa_fallback_serves_index_for_html_deep_link(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<html>spa</html>", encoding="utf-8")
    app = _make_app()

    with patch("dashboard.backend.main._INDEX", index):
        app.add_middleware(SpaFallbackMiddleware)
        client = TestClient(app)
        response = client.get("/alerts/foo", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert response.text == "<html>spa</html>"


def test_spa_fallback_skips_api_and_assets_paths(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<html>spa</html>", encoding="utf-8")
    app = _make_app()

    with patch("dashboard.backend.main._INDEX", index):
        app.add_middleware(SpaFallbackMiddleware)
        client = TestClient(app)
        api = client.get("/api/missing", headers={"Accept": "text/html"})
        assets = client.get("/assets/app.js", headers={"Accept": "text/html"})

    assert api.status_code == 404
    assert api.text == "missing"
    assert assets.status_code == 404
    assert assets.text == "missing"


def test_spa_fallback_skips_non_get_and_non_html(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<html>spa</html>", encoding="utf-8")
    app = _make_app()

    with patch("dashboard.backend.main._INDEX", index):
        app.add_middleware(SpaFallbackMiddleware)
        client = TestClient(app)
        post = client.post("/alerts/foo", headers={"Accept": "text/html"})
        json_get = client.get("/alerts/foo", headers={"Accept": "application/json"})

    assert post.status_code == 404
    assert post.text == "missing"
    assert json_get.status_code == 404
    assert json_get.text == "missing"


def test_spa_fallback_serves_index_for_default_accept_header(tmp_path: Path) -> None:
    """Browsers and TestClient often send Accept: */*; deep links must still resolve."""
    index = tmp_path / "index.html"
    index.write_text("<html>spa</html>", encoding="utf-8")
    app = _make_app()

    with patch("dashboard.backend.main._INDEX", index):
        app.add_middleware(SpaFallbackMiddleware)
        client = TestClient(app)
        response = client.get("/summary", headers={"Accept": "*/*"})

    assert response.status_code == 200
    assert response.text == "<html>spa</html>"


def test_spa_fallback_returns_original_404_when_index_missing(tmp_path: Path) -> None:
    missing_index = tmp_path / "does-not-exist.html"
    app = _make_app()

    with patch("dashboard.backend.main._INDEX", missing_index):
        app.add_middleware(SpaFallbackMiddleware)
        client = TestClient(app)
        response = client.get("/alerts/foo", headers={"Accept": "text/html"})

    assert response.status_code == 404
    assert response.text == "missing"
